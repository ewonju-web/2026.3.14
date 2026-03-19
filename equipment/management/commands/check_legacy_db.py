from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = "legacy MySQL(DB direct_nara_legacy) 연결 및 기본 테이블 개수 확인"

    def handle(self, *args, **options):
        legacy = connections["legacy"]
        self.stdout.write("legacy DB 접속 시도 중...")

        with legacy.cursor() as cursor:
            # 전체 테이블 수와 대표적인 테이블 이름 몇 개만 확인
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            self.stdout.write(self.style.SUCCESS(f"legacy DB 테이블 개수: {len(tables)}"))

            preview = ", ".join(tables[:10])
            self.stdout.write(f"일부 테이블: {preview}")

