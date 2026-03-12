# -*- coding: utf-8 -*-
"""
equipment_type='forklift'로 되어 있지만 모델명이 굴삭기(DX, 회링, 집게 등)인 매물을
excavator로 보정합니다. 지게차 탭 선택 시 굴삭기가 지게차로 보이던 문제 해결용.

사용법: python manage.py fix_excavator_misclassified_as_forklift [--dry-run]
"""
import re
from django.core.management.base import BaseCommand
from django.db.models import Q
from equipment.models import Equipment


# 굴삭기 패턴: 두산 DX, 회링, 집게, 굴삭기 등
EXCAVATOR_PATTERNS = [
    re.compile(r"DX\d", re.I),           # 두산 DX 시리즈
    re.compile(r"회링|코집|집게", re.I),
    re.compile(r"굴삭|미니굴|엑스카"),
]


def looks_like_excavator(model_name):
    if not (model_name or "").strip():
        return False
    for pat in EXCAVATOR_PATTERNS:
        if pat.search(model_name):
            return True
    return False


class Command(BaseCommand):
    help = "지게차로 잘못 분류된 굴삭기 매물을 excavator로 보정"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 대상만 출력")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = Equipment.objects.filter(equipment_type="forklift")
        to_fix = []
        for eq in qs:
            if looks_like_excavator(eq.model_name):
                to_fix.append(eq)

        self.stdout.write("보정 대상: %d건 (equipment_type=forklift 이지만 모델명이 굴삭기 패턴)" % len(to_fix))
        if dry_run:
            for eq in to_fix[:10]:
                self.stdout.write("  id=%s model=%s" % (eq.id, (eq.model_name or "")[:50]))
            if len(to_fix) > 10:
                self.stdout.write("  ... 외 %d건" % (len(to_fix) - 10))
            return

        updated = 0
        for eq in to_fix:
            eq.equipment_type = "excavator"
            eq.save(update_fields=["equipment_type"])
            updated += 1
        self.stdout.write("보정 완료: %d건 → equipment_type=excavator" % updated)
