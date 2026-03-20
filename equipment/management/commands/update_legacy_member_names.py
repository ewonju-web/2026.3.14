# -*- coding: utf-8 -*-
"""
이미 이관된 회원(legacy_member_id 있는 Profile)의 User.first_name을 채웁니다.
1) direct_nara 연결 가능 시: sw_member.mb_rname으로 보정
2) 불가 시: Profile.company_name(이관 시 저장된 이름)으로 보정
회원관리(관리자)에서 이름이 비어 있는 문제 해결용.

사용법: python manage.py update_legacy_member_names [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from equipment.models import Profile
import re

# Django mysql backend은 MySQLdb(mysqlclient)를 요구합니다.
# 운영 환경에 mysqlclient가 없을 수 있어, 필요 시 pymysql을 MySQLdb 대체로 등록합니다.
try:
    import MySQLdb  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except Exception:
        pass

User = get_user_model()


def run_sql(db_alias, sql, params=None):
    from django.db import connections
    with connections[db_alias].cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()


def looks_like_phone_number(raw):
    """이름으로 들어가면 안 되는 전화번호 형태(010 등)인지 대략 판별."""
    if not raw:
        return False
    digits = re.sub(r"[^0-9]", "", str(raw).strip())
    if not digits:
        return False
    if digits.startswith("010") and len(digits) == 11:
        return True
    if digits.startswith("0") and len(digits) in (10, 11):
        return True
    return False


def normalize_phone(raw):
    if not raw:
        return ""
    s = re.sub(r"[^0-9]", "", str(raw).strip())
    if s.startswith("82") and len(s) >= 10:
        s = "0" + s[2:]
    return s[:20]


class Command(BaseCommand):
    help = "direct_nara(sw_member) 기준으로 이름/상호를 보정(legacy id 없을 때도 phone 매칭)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="저장하지 않고 적용 대상만 출력",
        )
        parser.add_argument(
            "--sql-path",
            type=str,
            default="",
            help="direct_nara MySQL 접속이 안 될 때 사용할 sw_member SQL 덤프 경로(예: backup/extracted_db/direct_nara_backup/db_backup_*.sql)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        sql_path = options.get("sql_path") or ""

        # legacy_member_id가 비어있더라도(이관/마이그레이션 이후) admin에서 전화번호가 "이름"으로 보이는 케이스를 phone으로 보정
        profiles = Profile.objects.select_related("user").all()
        targets = []
        target_phones = set()
        for prof in profiles:
            first = (getattr(prof.user, "first_name", "") or "").strip()
            company = (prof.company_name or "").strip()
            if looks_like_phone_number(first) or looks_like_phone_number(company):
                targets.append(prof)
                ph = normalize_phone(getattr(prof, "phone", "") or "")
                if ph:
                    target_phones.add(ph)

        if not targets:
            self.stdout.write("보정 대상이 없습니다(이름 필드가 전화번호 형태가 아님).")
            return
        if not target_phones:
            self.stdout.write("보정 대상은 있으나 Profile.phone이 비어 있어 direct_nara 매칭이 불가능합니다.")
            return

        name_by_phone = {}
        try:
            from django.db import connections

            connections["direct_nara"].ensure_connection()
            rows = run_sql(
                "direct_nara",
                "SELECT mb_id, mb_tel, mb_hp, mb_rname, mb_name, mb_nicname FROM sw_member",
            )
            for row in rows:
                mb_id, mb_tel, mb_hp, mb_rname, mb_name, mb_nicname = (
                    row[0] or "",
                    row[1] or "",
                    row[2] or "",
                    row[3] or "",
                    row[4] or "",
                    row[5] or "",
                )
                # 이름 우선순위: 실명(mb_rname) -> 이름(mb_name) -> 닉네임(mb_nicname)
                # 닉네임이 이름 칼럼에 들어가는 문제를 줄이기 위해 mb_nicname은 마지막 fallback으로 둡니다.
                name = (mb_rname or "").strip()
                if not name or looks_like_phone_number(name):
                    name = (mb_name or "").strip()
                if not name or looks_like_phone_number(name):
                    name = (mb_nicname or "").strip()
                if not name or looks_like_phone_number(name):
                    continue
                for cand in (mb_hp, mb_tel, mb_id):
                    ph = normalize_phone(cand)
                    if ph and ph in target_phones and ph not in name_by_phone:
                        name_by_phone[ph] = name
                        break

            self.stdout.write("direct_nara에서 전화번호 기반 이름을 %d건 매칭" % len(name_by_phone))
        except Exception as e:
            self.stdout.write("direct_nara 매칭 실패: %s" % e)

            # fallback: SQL 덤프에서 sw_member를 phone 기준으로 직접 파싱
            if not sql_path:
                self.stdout.write("sql-path가 지정되지 않아 보정을 중단합니다.")
                return

            import os

            if not os.path.exists(sql_path):
                self.stdout.write("sql-path 파일이 없습니다: %s" % sql_path)
                return

            # sw_member 컬럼 순서: (mb_num, mb_id, mb_pwd, mb_name, mb_rname, mb_nicname, ...)
            # INSERT는 대개 한 줄에 VALUES 튜플이 연속으로 들어있기 때문에, 라인 단위로 우선 파싱합니다.
            tuple_re = re.compile(
                r"\((\d+),'((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)'"
            )

            def unescape_mysql(s: str) -> str:
                # mysqldump에서 \\' , \\\\ 형태가 섞일 수 있어 간단히만 되돌립니다.
                return s.replace("\\'", "'").replace("\\\\", "\\")

            def build_from_sql(path: str):
                mapping = {}
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "INSERT INTO `sw_member` VALUES" not in line:
                            continue
                        for m in tuple_re.finditer(line):
                            mb_id = unescape_mysql(m.group(2))
                            mb_name = unescape_mysql(m.group(4))
                            mb_rname = unescape_mysql(m.group(5))
                            mb_nicname = unescape_mysql(m.group(6))

                            ph = normalize_phone(mb_id)
                            if not ph or ph not in target_phones or ph in mapping:
                                continue

                            # SQL 덤프 fallback도 동일한 우선순위 적용
                            name = (mb_rname or "").strip() or (mb_name or "").strip() or (mb_nicname or "").strip()
                            if not name or looks_like_phone_number(name):
                                continue
                            mapping[ph] = name
                            if len(mapping) == len(target_phones):
                                return mapping
                return mapping

            name_by_phone = build_from_sql(sql_path)
            self.stdout.write("SQL 덤프에서 전화번호 기반 이름을 %d건 매칭" % len(name_by_phone))

        updated = 0
        for prof in targets:
            user = prof.user
            ph = normalize_phone(getattr(prof, "phone", "") or "")
            matched_name = name_by_phone.get(ph)
            if not matched_name:
                continue

            first_name_val = (matched_name or "").strip()[:30]
            company_name_val = (matched_name or "").strip()[:100]

            first = (user.first_name or "").strip()
            company = (prof.company_name or "").strip()
            should_update_first = looks_like_phone_number(first) or not first
            should_update_company = looks_like_phone_number(company) or not company

            if not (should_update_first or should_update_company):
                continue

            if dry_run:
                self.stdout.write(
                    "보정 대상: username=%s phone=%s → first_name=%s company_name=%s"
                    % (user.username, ph, first_name_val, company_name_val)
                )
                updated += 1
                continue

            if should_update_first:
                user.first_name = first_name_val
                user.save(update_fields=["first_name"])
            if should_update_company:
                prof.company_name = company_name_val
                prof.save(update_fields=["company_name"])
            updated += 1

        self.stdout.write("이름 보정 완료: %d명" % updated)
