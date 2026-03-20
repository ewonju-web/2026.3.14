# -*- coding: utf-8 -*-
"""
백업 SQL(sw_member INSERT)에서 전화번호 기준으로 리뉴얼 회원 정보를 보정.

반영 항목:
- Profile.legacy_member_id: sw_member.mb_num
- User.first_name: 이름(우선순위: mb_name > mb_rname > mb_nicname)
- User.last_name: 닉네임(mb_nicname)
- User.date_joined: 가입일(mb_login)
- Profile.company_name: 닉네임(비어 있을 때만)
"""
import re
from datetime import datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from equipment.models import Profile

User = get_user_model()


def normalize_phone(raw):
    if not raw:
        return ""
    s = re.sub(r"[^0-9]", "", str(raw).strip())
    if s.startswith("82") and len(s) >= 10:
        s = "0" + s[2:]
    return s[:20]


def parse_joined(value):
    """
    sw_member.mb_login 파싱.
    예: '2020-10-16 10:02:29'
    """
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
        return timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        return None


class Command(BaseCommand):
    help = "백업 SQL로 이름/닉네임/가입일/회원번호(legacy id) 보정"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sql-path",
            type=str,
            required=True,
            help="sw_member INSERT가 포함된 SQL 파일 경로",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="저장 없이 대상만 확인",
        )
        parser.add_argument(
            "--force-name",
            action="store_true",
            help="기존 이름이 있어도 SQL의 이름(mb_name 우선)으로 강제 덮어쓰기",
        )

    def handle(self, *args, **options):
        sql_path = options["sql_path"]
        dry_run = options["dry_run"]
        force_name = options.get("force_name", False)

        tuple_re = re.compile(
            r"\((\d+),'((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)'"
            r",'((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)'"
            r",'((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)','((?:\\.|[^'])*)"
        )

        def unescape_mysql(s):
            return (s or "").replace("\\'", "'").replace("\\\\", "\\")

        # phone -> member data
        member_by_phone = {}

        with open(sql_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "INSERT INTO `sw_member` VALUES" not in line:
                    continue
                for m in tuple_re.finditer(line):
                    mb_num = int(m.group(1))
                    mb_id = unescape_mysql(m.group(2))
                    mb_name = unescape_mysql(m.group(4))
                    mb_rname = unescape_mysql(m.group(5))
                    mb_nicname = unescape_mysql(m.group(6))
                    mb_tel = unescape_mysql(m.group(10))
                    mb_hp = unescape_mysql(m.group(11))
                    mb_login = unescape_mysql(m.group(17))

                    phone = normalize_phone(mb_hp) or normalize_phone(mb_tel) or normalize_phone(mb_id)
                    if not phone:
                        continue
                    if phone in member_by_phone:
                        continue

                    display_name = (mb_name or "").strip() or (mb_rname or "").strip() or (mb_nicname or "").strip() or "회원"
                    nickname = (mb_nicname or "").strip()
                    joined_at = parse_joined(mb_login)

                    member_by_phone[phone] = {
                        "mb_num": mb_num,
                        "name": display_name[:30],
                        "nickname": nickname[:50],
                        "joined_at": joined_at,
                    }

        total = 0
        updated = 0
        for prof in Profile.objects.select_related("user").all():
            phone = normalize_phone(prof.phone) or normalize_phone(prof.user.username)
            if not phone or phone not in member_by_phone:
                continue
            total += 1
            data = member_by_phone[phone]
            user = prof.user

            changed_user_fields = []
            changed_profile_fields = []

            if prof.legacy_member_id != data["mb_num"]:
                prof.legacy_member_id = data["mb_num"]
                changed_profile_fields.append("legacy_member_id")

            if data["name"] and (
                force_name
                or (not user.first_name or user.first_name == "회원")
            ):
                user.first_name = data["name"]
                changed_user_fields.append("first_name")

            if data["nickname"] and not user.last_name:
                user.last_name = data["nickname"]
                changed_user_fields.append("last_name")

            if data["joined_at"] and user.date_joined != data["joined_at"]:
                user.date_joined = data["joined_at"]
                changed_user_fields.append("date_joined")

            if data["nickname"] and not (prof.company_name or "").strip():
                prof.company_name = data["nickname"][:100]
                changed_profile_fields.append("company_name")

            if changed_user_fields or changed_profile_fields:
                updated += 1
                if dry_run:
                    continue
                if changed_user_fields:
                    user.save(update_fields=changed_user_fields)
                if changed_profile_fields:
                    prof.save(update_fields=changed_profile_fields)

        suffix = " (dry-run)" if dry_run else ""
        self.stdout.write(f"SQL 매칭 {total}건, 실제 보정 {updated}건{suffix}")

