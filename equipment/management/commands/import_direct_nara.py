# -*- coding: utf-8 -*-
# mysqlclient 없을 때 PyMySQL로 대체 (pip install pymysql)
try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

"""
기존 direct-nara DB(sw_member, tb_pro) → 리뉴얼 회원·매물 이관.
사용법: python manage.py import_direct_nara / --listings-only / --dry-run --limit N
"""
import re
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import connection, transaction, IntegrityError
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, get_current_timezone
from equipment.models import Profile, Equipment, EquipmentType, ListingStatus

User = get_user_model()


def parse_sdate_to_created_at(sdate):
    """tb_pro.sdate → timezone-aware datetime for Equipment.created_at"""
    if sdate is None:
        return None
    if hasattr(sdate, "isoformat"):  # date or datetime
        if hasattr(sdate, "hour"):
            dt = sdate
        else:
            dt = datetime.combine(sdate, datetime.min.time())
        if dt.tzinfo is None:
            return make_aware(dt, get_current_timezone())
        return dt
    s = str(sdate).strip()[:19]
    if not s:
        return None
    parsed = parse_datetime(s)
    if parsed and parsed.tzinfo is None:
        return make_aware(parsed, get_current_timezone())
    return parsed


def normalize_phone(raw):
    if not raw:
        return ""
    # legacy DB에 전화번호가 공백/하이픈뿐 아니라 점(.) 등으로 섞여 있을 수 있어
    # 매칭이 실패하지 않도록 "숫자만" 추출한다.
    s = re.sub(r"[^0-9]", "", str(raw).strip())
    # 국가코드(82) 형태 제거: 8210xxxxxxx -> 010xxxxxxx
    if s.startswith("82") and len(s) >= 10:
        s = "0" + s[2:]
    return s[:20]  # 필드 길이 제한


def looks_like_phone_number(raw):
    """이름으로 들어가면 안 되는 전화번호 형태(010 등)인지 대략 판별."""
    if not raw:
        return False
    digits = re.sub(r"[^0-9]", "", str(raw).strip())
    if not digits:
        return False
    # 한국 휴대폰: 010XXXXXXXX (11자리)
    if digits.startswith("010") and len(digits) == 11:
        return True
    # 기타 전화번호(하이픈 제거 후)도 10~11자리 + 앞자리 0이면 전화로 취급
    if digits.startswith("0") and len(digits) in (10, 11):
        return True
    return False


# direct-nara tb_pro.cate1 → EquipmentType
CATE_TO_TYPE = {
    "1": EquipmentType.EXCAVATOR,
    "2": EquipmentType.FORKLIFT,
    "4": EquipmentType.EXCAVATOR,
    "12": EquipmentType.EXCAVATOR,
    "3": EquipmentType.DUMP,
    "5": EquipmentType.LOADER,
    "6": EquipmentType.ATTACHMENT,
}


def run_sql(db_alias, sql, params=None):
    from django.db import connections
    with connections[db_alias].cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()


class Command(BaseCommand):
    help = "direct-nara DB(sw_member, tb_pro) → 회원·매물 이관 (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--listings-only",
            action="store_true",
            help="회원 이관 건너뛰고 매물만 이관 (기존 회원 매핑 사용)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 처리할 건수만 출력",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="회원/매물 각각 최대 처리 건수 (0=전체)",
        )

    def handle(self, *args, **options):
        listings_only = options["listings_only"]
        dry_run = options["dry_run"]
        limit = options["limit"] or 999999

        try:
            from django.db import connections
            connections["direct_nara"].ensure_connection()
        except Exception as e:
            self.stderr.write(
                "direct_nara DB 연결 실패. settings.DATABASES['direct_nara'] 및 pip install mysqlclient 확인. %s" % e
            )
            return

        if dry_run:
            self.stdout.write("(dry-run: 저장하지 않음)")

        member_map = {}  # legacy_member_id (mb_num) -> User
        phone_to_user = {}  # normalized_phone -> User

        if not listings_only:
            # ----- 회원 이관 -----
            rows = run_sql(
                "direct_nara",
                "SELECT mb_num, mb_id, mb_tel, mb_hp, mb_rname, mb_name, mb_nicname FROM sw_member ORDER BY mb_num"
            )
            if limit < 999999:
                rows = rows[:limit]
            self.stdout.write("회원 %d명 읽음 (direct_nara.sw_member)" % len(rows))

            for row in rows:
                mb_num, mb_id, mb_tel, mb_hp, mb_rname, mb_name, mb_nicname = (
                    row[0],
                    row[1] or "",
                    row[2] or "",
                    row[3] or "",
                    row[4] or "",
                    row[5] or "",
                    row[6] or "",
                )
                phone = normalize_phone(mb_hp) or normalize_phone(mb_tel) or normalize_phone(mb_id)

                # sw_member:
                # - mb_rname: 실명(비어 있는 케이스가 많음)
                # - mb_name: 이름
                # - mb_nicname: 닉네임
                # 이름 칼럼에는 실명/이름 우선으로 넣고, 닉네임은 마지막 fallback으로만 사용.
                name = (mb_rname or "").strip()
                if not name:
                    name = (mb_name or "").strip()
                if not name:
                    name = (mb_nicname or "").strip()
                if not name:
                    cand = (mb_id or "").strip()
                    if cand and not looks_like_phone_number(cand):
                        name = cand
                # 최종적으로도 전화번호 형태면 보정 대상에서 제외
                if looks_like_phone_number(name):
                    name = "회원"

                existing = Profile.objects.filter(legacy_member_id=mb_num).first()
                if existing:
                    # 회원관리 등에서 이름 표시를 위해 User.first_name 보정
                    if name and (not existing.user.first_name or existing.user.first_name == "회원"):
                        existing.user.first_name = name[:30]
                        existing.user.save(update_fields=["first_name"])
                    member_map[mb_num] = existing.user
                    if phone:
                        phone_to_user[phone] = existing.user
                    continue

                if dry_run:
                    member_map[mb_num] = None
                    continue

                # 항상 legacy_mb_num 사용해 username 중복 방지 (전화번호는 Profile.phone에 저장)
                username = "legacy_%s" % mb_num
                # 이미 다른 User에 붙어 있는 Profile(legacy_member_id)이 있으면 그 User 사용
                existing_prof = Profile.objects.filter(legacy_member_id=mb_num).first()
                if existing_prof:
                    if name and (not existing_prof.user.first_name or existing_prof.user.first_name == "회원"):
                        existing_prof.user.first_name = name[:30]
                        existing_prof.user.save(update_fields=["first_name"])
                    member_map[mb_num] = existing_prof.user
                    if phone:
                        phone_to_user[phone] = existing_prof.user
                    continue
                if User.objects.filter(username=username).exists():
                    user = User.objects.get(username=username)
                    # 회원관리에서 이름 표시를 위해 first_name 갱신
                    if name:
                        user.first_name = name[:30]
                        user.save(update_fields=["first_name"])
                    prof = Profile.objects.filter(user=user).first()
                    if prof:
                        prof.legacy_member_id = mb_num
                        prof.phone = phone or ""
                        prof.company_name = name[:100]
                        prof.save()
                    else:
                        try:
                            prof = Profile.objects.create(
                                user=user,
                                legacy_member_id=mb_num,
                                phone=phone or "",
                                company_name=name[:100],
                            )
                        except IntegrityError:
                            prof = Profile.objects.filter(legacy_member_id=mb_num).first()
                            if prof:
                                user = prof.user
                    member_map[mb_num] = user
                    if phone:
                        phone_to_user[phone] = user
                    continue
                user = None
                try:
                    user = User.objects.create_user(
                        username=username,
                        password="!migrated_no_login",  # 곧바로 set_unusable_password 처리
                        first_name=name[:30],
                    )
                    user.set_unusable_password()
                    user.save()
                except IntegrityError:
                    # username 중복(이전 실행/동일 mb_num 재처리): 기존 User 사용
                    user = User.objects.filter(username=username).first()
                    if not user:
                        raise
                    if name:
                        user.first_name = name[:30]
                        user.save(update_fields=["first_name"])

                try:
                    prof, created = Profile.objects.get_or_create(
                        user=user,
                        defaults={
                            "legacy_member_id": mb_num,
                            "phone": phone or "",
                            "company_name": name[:100],
                        },
                    )
                    if not created:
                        prof.legacy_member_id = mb_num
                        prof.phone = phone or ""
                        prof.company_name = name[:100]
                        prof.save()
                except IntegrityError:
                    # legacy_member_id 중복(이전 실행·중복 데이터): 기존 Profile 사용
                    prof = Profile.objects.filter(legacy_member_id=mb_num).first()
                    if prof:
                        user = prof.user
                    else:
                        raise
                member_map[mb_num] = user
                if phone:
                    phone_to_user[phone] = user

            self.stdout.write("회원 이관 완료: %d명" % len(member_map))

        # listings_only면 기존 Profile에서 전화번호→User 매핑 구성
        if listings_only and not phone_to_user:
            for p in Profile.objects.select_related("user").exclude(phone__isnull=True).exclude(phone=""):
                ph = normalize_phone(p.phone)
                if ph:
                    phone_to_user[ph] = p.user

        # ----- 매물 이관 (전화번호로 작성자 매칭) -----
        rows = run_sql(
            "direct_nara",
            "SELECT uid, cate1, model, buyprice, sdate, uname, utel, city, county, content, nara_ing FROM tb_pro ORDER BY uid"
        )
        if limit < 999999:
            rows = rows[:limit]
        self.stdout.write("매물 %d건 읽음 (direct_nara.tb_pro)" % len(rows))

        created = 0
        skipped = 0
        no_author = 0

        for row in rows:
            uid, cate1, model, buyprice, sdate, uname, utel, city, county, content, nara_ing = (
                row[0], row[1] or "", row[2] or "", row[3] or 0, row[4] or "", row[5] or "", row[6] or "",
                row[7] or "", row[8] or "", row[9] or "", row[10] or "판매중",
            )

            if Equipment.objects.filter(legacy_listing_id=uid).exists():
                skipped += 1
                continue

            author = None
            if utel:
                ph = normalize_phone(utel)
                author = phone_to_user.get(ph)
                if not author:
                    for p in Profile.objects.filter(legacy_member_id__isnull=False).select_related("user"):
                        if normalize_phone(getattr(p, "phone", "") or "") == ph:
                            phone_to_user[ph] = p.user
                            author = p.user
                            break

            if not author:
                no_author += 1

            if dry_run:
                created += 1
                continue

            eq_type = CATE_TO_TYPE.get(str(cate1), EquipmentType.EXCAVATOR)
            try:
                year = int(str(sdate)[:4]) if sdate and str(sdate)[:4].isdigit() else None
            except Exception:
                year = None

            try:
                eq = Equipment.objects.create(
                    legacy_listing_id=uid,
                    author=author,
                    equipment_type=eq_type,
                    model_name=(model or "")[:100],
                    listing_price=abs(int(buyprice)) if buyprice else 0,
                    year_manufactured=year,
                    current_location=(city or "") + " " + (county or ""),
                    description=(content or "")[:50],
                    is_sold=(nara_ing == "판매완료"),
                    listing_status=ListingStatus.NORMAL,
                )
                created += 1
                # 기존 사이트 작성일(sdate) → 리뉴얼 created_at 반영
                parsed = parse_sdate_to_created_at(sdate)
                if parsed:
                    eq.created_at = parsed
                    eq.save(update_fields=["created_at"])
            except IntegrityError:
                skipped += 1

        self.stdout.write("매물 이관: 생성 %d, 스킵(기존) %d, 작성자 없음 %d" % (created, skipped, no_author))
