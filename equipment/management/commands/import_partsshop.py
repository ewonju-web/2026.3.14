# -*- coding: utf-8 -*-
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from equipment.models import PartsShop


def _to_float(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _normalize_phone(value):
    return (value or "").strip()


def _detect_shop_kind(keyword_text):
    text = (keyword_text or "").upper()
    # 수리/AS/정비 계열이 하나라도 있으면 AS센터 우선
    if any(token in text for token in ("수리", "AS", "정비")):
        return "as"
    if "부품" in text:
        return "parts"
    return "parts"


def _detect_equipment_types(keyword_text):
    text = (keyword_text or "").strip()
    if not text:
        return ["excavator"]

    if ("중장비" in text) or ("건설기계" in text):
        return ["excavator", "dump", "forklift", "crane", "skidloader"]
    if ("굴삭기" in text) or ("포크레인" in text):
        return ["excavator"]
    if ("덤프트럭" in text) or ("덤프" in text):
        return ["dump"]
    if "지게차" in text:
        return ["forklift"]
    if "크레인" in text:
        return ["crane"]
    if ("스키로더" in text) or ("로더" in text):
        return ["skidloader"]
    return ["excavator"]


class Command(BaseCommand):
    help = "전국_중장비업체.csv 파일을 PartsShop으로 일괄 import"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default="전국_중장비업체.csv",
            help="CSV 파일 경로 (기본: 전국_중장비업체.csv)",
        )

    def handle(self, *args, **options):
        csv_arg = (options.get("csv") or "").strip()
        csv_path = Path(csv_arg)
        if not csv_path.is_absolute():
            csv_path = Path(settings.BASE_DIR) / csv_path
        if not csv_path.is_file():
            raise CommandError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

        rows = None
        for enc in ("utf-8-sig", "cp949", "euc-kr"):
            try:
                with csv_path.open("r", encoding=enc, newline="") as f:
                    rows = list(csv.DictReader(f))
                self.stdout.write(f"CSV 인코딩 감지: {enc}")
                break
            except UnicodeDecodeError:
                continue
        if rows is None:
            raise CommandError("CSV 인코딩을 읽을 수 없습니다. utf-8-sig/cp949/euc-kr를 확인해 주세요.")

        required_columns = {"업체명", "전화번호", "주소", "위도", "경도", "지역", "키워드"}
        fieldnames = set(rows[0].keys()) if rows else set()
        missing = sorted(required_columns - fieldnames)
        if missing:
            raise CommandError(f"CSV 컬럼이 누락되었습니다: {', '.join(missing)}")

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in rows:
            name = (row.get("업체명") or "").strip()
            contact = _normalize_phone(row.get("전화번호"))
            if not name or not contact:
                skipped_count += 1
                continue

            keyword_text = (row.get("키워드") or "").strip()
            shop_kind = _detect_shop_kind(keyword_text)
            defaults = {
                "shop_kind": shop_kind,
                "region": (row.get("지역") or "").strip(),
                "equipment_types": _detect_equipment_types(keyword_text),
                "address": (row.get("주소") or "").strip(),
                "lat": _to_float(row.get("위도")),
                "lng": _to_float(row.get("경도")),
                "note": keyword_text,
            }

            obj, created = PartsShop.objects.get_or_create(
                name=name,
                contact=contact,
                defaults=defaults,
            )
            if created:
                created_count += 1
                continue

            changed = False
            for key, value in defaults.items():
                if getattr(obj, key) != value:
                    setattr(obj, key, value)
                    changed = True
            if changed:
                obj.save(update_fields=list(defaults.keys()))
                updated_count += 1

        self.stdout.write(self.style.SUCCESS("PartsShop CSV import 완료"))
        self.stdout.write(f"- 생성: {created_count}")
        self.stdout.write(f"- 갱신: {updated_count}")
        self.stdout.write(f"- 스킵(업체명/전화번호 없음): {skipped_count}")
