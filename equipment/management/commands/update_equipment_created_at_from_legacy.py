# -*- coding: utf-8 -*-
"""
이미 이관된 매물(legacy_listing_id 있음)의 작성일(created_at)을 기존 사이트(tb_pro.sdate) 기준으로 보정.
direct_nara DB 연결 필요. 사용: python manage.py update_equipment_created_at_from_legacy [--dry-run]
"""
try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, get_current_timezone
from equipment.models import Equipment
from equipment.management.commands.import_direct_nara import run_sql, parse_sdate_to_created_at


class Command(BaseCommand):
    help = "이관된 매물의 작성일(created_at)을 tb_pro.sdate 기준으로 보정"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="실제 저장 없이 대상만 출력")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("(dry-run: 저장하지 않음)")

        try:
            from django.db import connections
            connections["direct_nara"].ensure_connection()
        except Exception as e:
            self.stderr.write("direct_nara DB 연결 실패. settings.DATABASES['direct_nara'] 확인. %s" % e)
            return

        qs = Equipment.objects.filter(legacy_listing_id__isnull=False).exclude(legacy_listing_id=0)
        ids = list(qs.values_list("legacy_listing_id", flat=True))
        if not ids:
            self.stdout.write("legacy_listing_id가 있는 매물이 없습니다.")
            return

        # tb_pro에서 uid, sdate 한 번에 조회 (IN 절은 1000개 단위로)
        updated = 0
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            placeholders = ",".join(["%s"] * len(chunk))
            rows = run_sql("direct_nara", "SELECT uid, sdate FROM tb_pro WHERE uid IN (%s)" % placeholders, chunk)
            for uid, sdate in rows:
                parsed = parse_sdate_to_created_at(sdate)
                if not parsed:
                    continue
                eq = Equipment.objects.filter(legacy_listing_id=uid).first()
                if not eq or eq.created_at == parsed:
                    continue
                if not dry_run:
                    eq.created_at = parsed
                    eq.save(update_fields=["created_at"])
                updated += 1

        self.stdout.write(self.style.SUCCESS("작성일 보정: %d건" % updated + (" (dry-run)" if dry_run else "")))
