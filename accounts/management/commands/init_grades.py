"""
등급 초기 데이터 생성: 일반회원, 매매상
사용: python manage.py init_grades
"""
from django.core.management.base import BaseCommand
from accounts.models import MembershipGrade


class Command(BaseCommand):
    help = "회원 등급 초기 데이터 생성 (일반회원, 매매상)"

    def handle(self, *args, **options):
        grades = [
            {
                "code": "normal",
                "name": "일반회원",
                "is_paid": False,
                "max_listings": 5,
                "description": "무료 회원. 매물 등록 수 제한.",
                "sort_order": 0,
            },
            {
                "code": "dealer",
                "name": "매매상",
                "is_paid": True,
                "max_listings": None,
                "description": "정액제 유료 회원. 매물 무제한 등록 등.",
                "sort_order": 1,
            },
        ]
        for g in grades:
            obj, created = MembershipGrade.objects.update_or_create(
                code=g["code"],
                defaults={
                    "name": g["name"],
                    "is_paid": g["is_paid"],
                    "max_listings": g["max_listings"],
                    "description": g["description"],
                    "sort_order": g["sort_order"],
                },
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'Created' if created else 'Updated'}: {obj}")
            )
