# -*- coding: utf-8 -*-
"""
이관된 매물(legacy_listing_id 있음)의 제조사를 model_name으로 추정해 채움.
tb_pro에 제조사 컬럼이 없어 이관 시 비어 있었음.
사용법: python manage.py update_legacy_manufacturer [--dry-run]
"""
import re
from django.core.management.base import BaseCommand
from django.db.models import Q

from equipment.models import Equipment


# model_name 앞부분/포함 문자열 → 제조사 (대소문자 무시, 순서 유지)
# 구보다(쿠보타) 미니굴 U10~U50을 HD 현대보다 먼저 매칭
MANUFACTURER_PATTERNS = [
    (r"구보다|쿠보타|KUBOTA|^U1\d|^U2\d|^U3\d|^U5\d", "구보다"),
    (r"^HX|^HX-|^HW|^U\d|^U-|현대", "HD 현대"),
    (r"^ZX|^ZX-|히타치", "히타치"),
    (r"^EC\d|^EC-|^EC\b|볼보", "볼보"),
    (r"^KX|^kx|코벨코|고베코", "코벨코"),
    (r"얀마|YANMAR|^VIO", "얀마"),  # 얀마 ViO 시리즈(VIO17, VIO35 등) → 비오렐보다 먼저
    (r"^VI\b|^Vi\b|^vi\b|^Vio|비오렐", "비오렐"),
    (r"^CAT\b|캐터필러|^320|^320D|^329", "캐터필러"),
    (r"^DH|^DX|두산", "두산"),
    (r"^PC\d|^PC-|코맥스", "코맥스"),
    (r"^밥캣|^BOBCAT", "밥캣"),
    (r"^구보", "구보"),  # 구보(다) 제외한 구보 계열
    (r"^솔라", "솔라"),
    (r"^R\d{2,4}\b|^RC\d|^RX\d|^RH\d|^RW\d|^R\d\b", "기타"),
    (r"^SK|^SK-", "SK"),
    (r"^커민스|^CUMMINS", "커민스"),
    (r"^벤츠|^메르세데스", "메르세데스"),
    (r"^타다노|^TADANO", "타다노"),
    (r"^도요타|^토요타", "도요타"),
    (r"^니산|^NISSAN", "니산"),
    (r"^클라크|^CLARK", "클라크"),
    (r"^린드이|^LINDE", "린드이"),
    (r"^한일|^한일지게차", "한일"),
    (r"^삼성|^SAMSUNG", "삼성"),
    (r"^대우", "대우"),
    (r"^LS|^LS트랙터", "LS"),
    (r"^유니콘|^UNICON", "유니콘"),
]


def guess_manufacturer(model_name):
    if not (model_name and model_name.strip()):
        return ""
    name = (model_name or "").strip()
    for pattern, maker in MANUFACTURER_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return maker
    return ""


class Command(BaseCommand):
    help = "legacy 매물의 제조사를 model_name으로 추정해 업데이트"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 적용 대상만 출력")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        # 1) 비어 있는 제조사 채우기
        qs = Equipment.objects.filter(legacy_listing_id__isnull=False).filter(
            Q(manufacturer__isnull=True) | Q(manufacturer="")
        )
        total = qs.count()
        updated = 0
        no_guess = 0
        for eq in qs:
            guessed = guess_manufacturer(eq.model_name)
            if guessed:
                if not dry_run:
                    eq.manufacturer = guessed[:50]
                    eq.save(update_fields=["manufacturer"])
                updated += 1
            else:
                no_guess += 1
        # 2) 잘못 "HD 현대"로 들어간 구보다 매물 보정
        kubota_pattern = re.compile(r"구보다|쿠보타|KUBOTA|^U1\d|^U2\d|^U3\d|^U5\d", re.IGNORECASE)
        wrong_hyundai = Equipment.objects.filter(
            legacy_listing_id__isnull=False,
            manufacturer__in=("HD 현대", "현대"),
        )
        fixed = 0
        for eq in wrong_hyundai:
            if eq.model_name and kubota_pattern.search(eq.model_name.strip()):
                if not dry_run:
                    eq.manufacturer = "구보다"
                    eq.save(update_fields=["manufacturer"])
                fixed += 1
        # 3) 잘못 "비오렐"로 들어간 얀마(VIO 시리즈) 보정
        yanmar_pattern = re.compile(r"얀마|YANMAR|^VIO", re.IGNORECASE)
        wrong_vio = Equipment.objects.filter(
            legacy_listing_id__isnull=False,
            manufacturer="비오렐",
        )
        fixed_yanmar = 0
        for eq in wrong_vio:
            if eq.model_name and yanmar_pattern.search(eq.model_name.strip()):
                if not dry_run:
                    eq.manufacturer = "얀마"
                    eq.save(update_fields=["manufacturer"])
                fixed_yanmar += 1
        self.stdout.write(
            "대상(제조사 비어 있음) %d건 → 추정 반영 %d건, 추정 불가 %d건%s"
            % (total, updated, no_guess, " (dry-run)" if dry_run else "")
        )
        if fixed:
            self.stdout.write("구보다로 보정(기존 HD 현대→구보다): %d건%s" % (fixed, " (dry-run)" if dry_run else ""))
        if fixed_yanmar:
            self.stdout.write("얀마로 보정(기존 비오렐→얀마): %d건%s" % (fixed_yanmar, " (dry-run)" if dry_run else ""))
