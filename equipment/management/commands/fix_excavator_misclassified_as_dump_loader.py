# -*- coding: utf-8 -*-
"""
덤프트럭/로더(및 기타 비굴삭기 카테고리)로 잘못 분류된 굴삭기 매물을 excavator로 보정.

판단 기준:
- sub_type 또는 weight_class 코드가 EXC_* 인 경우
- 모델명이 굴삭기 시리즈 패턴(DX/EC/HX/S55V 등)인 경우

사용법:
  python manage.py fix_excavator_misclassified_as_dump_loader --dry-run
  python manage.py fix_excavator_misclassified_as_dump_loader
"""
import re

from django.core.management.base import BaseCommand
from django.db.models import Q

from equipment.models import Equipment


TARGET_TYPES = ("dump", "loader", "crane", "other")
EXCAVATOR_PATTERNS = [
    re.compile(r"DX\d", re.I),
    re.compile(r"EC\d", re.I),
    re.compile(r"HX\d", re.I),
    re.compile(r"S\d{2,3}V", re.I),
    re.compile(r"MX\d", re.I),
    re.compile(r"굴삭|미니굴|회링|집게"),
]


class Command(BaseCommand):
    help = "덤프트럭/로더 등으로 잘못 분류된 굴삭기 매물을 excavator로 보정"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장 없이 대상만 출력")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        base_qs = Equipment.objects.filter(equipment_type__in=TARGET_TYPES).order_by("id")
        to_fix = []
        for eq in base_qs:
            is_exc_code = (eq.sub_type or "").startswith("EXC_") or (eq.weight_class or "").startswith("EXC_")
            is_exc_model = any(p.search(eq.model_name or "") for p in EXCAVATOR_PATTERNS)
            if is_exc_code or is_exc_model:
                to_fix.append(eq)

        total = len(to_fix)
        self.stdout.write(
            "보정 대상: %d건 (type in %s, EXC_* 코드 또는 굴삭기 모델 패턴)"
            % (total, ",".join(TARGET_TYPES))
        )

        if dry_run:
            for eq in to_fix[:20]:
                self.stdout.write(
                    "  id=%s type=%s model=%s sub=%s weight=%s"
                    % (
                        eq.id,
                        eq.equipment_type,
                        (eq.model_name or "")[:40],
                        (eq.sub_type or "")[:20],
                        (eq.weight_class or "")[:20],
                    )
                )
            if total > 20:
                self.stdout.write("  ... 외 %d건" % (total - 20))
            return

        updated = 0
        for eq in to_fix:
            eq.equipment_type = "excavator"
            eq.save(update_fields=["equipment_type"])
            updated += 1
        self.stdout.write("보정 완료: %d건 → equipment_type=excavator" % updated)
