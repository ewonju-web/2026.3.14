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

User = get_user_model()


def run_sql(db_alias, sql, params=None):
    from django.db import connections
    with connections[db_alias].cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchall()


class Command(BaseCommand):
    help = "legacy 회원의 User.first_name 보정 (direct_nara 또는 Profile.company_name)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="저장하지 않고 적용 대상만 출력",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        profiles = Profile.objects.filter(legacy_member_id__isnull=False).select_related("user")
        if not profiles.exists():
            self.stdout.write("legacy_member_id가 있는 회원이 없습니다.")
            return

        name_by_mb = {}
        try:
            from django.db import connections
            connections["direct_nara"].ensure_connection()
            mb_ids = list(profiles.values_list("legacy_member_id", flat=True).distinct())
            placeholders = ",".join(["%s"] * len(mb_ids))
            rows = run_sql(
                "direct_nara",
                "SELECT mb_num, mb_id, mb_tel, mb_hp, mb_rname FROM sw_member WHERE mb_num IN (%s)" % placeholders,
                mb_ids,
            )
            for row in rows:
                mb_num, mb_id, mb_tel, mb_hp, mb_rname = (row[0], row[1] or "", row[2] or "", row[3] or "", row[4] or "")
                name = (mb_rname or mb_id or "").strip() or "회원"
                name_by_mb[mb_num] = (name[:30], name[:100])
            self.stdout.write("direct_nara에서 %d명 이름 조회" % len(name_by_mb))
        except Exception as e:
            self.stdout.write("direct_nara 미사용: %s" % e)

        updated = 0
        for prof in profiles:
            user = prof.user
            first_name_val = None
            if prof.legacy_member_id in name_by_mb:
                fn, cn = name_by_mb[prof.legacy_member_id]
                if fn and fn != "회원":
                    first_name_val = fn
            if first_name_val is None and prof.company_name and prof.company_name.strip() and prof.company_name != "회원":
                first_name_val = (prof.company_name or "").strip()[:30]

            if not first_name_val:
                continue
            if user.first_name and user.first_name.strip() and user.first_name != "회원":
                continue

            if dry_run:
                self.stdout.write("보정 대상: username=%s → first_name=%s" % (user.username, first_name_val))
                updated += 1
                continue
            user.first_name = first_name_val
            user.save(update_fields=["first_name"])
            updated += 1

        self.stdout.write("이름 보정 완료: %d명" % updated)
