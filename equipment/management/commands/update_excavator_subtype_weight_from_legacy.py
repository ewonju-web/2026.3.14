"""
legacy(tb_pro) → 리뉴얼 Equipment.sub_type/weight_class 보정.

현재 이관(import_direct_nara) 시 sub_type/weight_class가 비어 있어서
UI 필터(타이어식/크롤러식 + 톤수/중량)가 0건으로 나오는 문제를 해결합니다.

전제:
- Equipment.legacy_listing_id = tb_pro.uid 로 매칭되어 있음
- Excavator 필터 값은 templates/equipment/equipment_list.html 의 코드 기준
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connections, transaction

from equipment.models import Equipment


class Command(BaseCommand):
    help = "legacy tb_pro 기반으로 Equipment(sub_type/weight_class) 채우기"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 대상만 처리 로그 출력")
        parser.add_argument("--limit", type=int, default=0, help="처리할 Equipment 수 제한(0=전체)")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"] or 0

        # templates/equipment/equipment_list.html 기준 코드
        EXC_TIRE = "EXC_TIRE"
        EXC_CRAWLER = "EXC_CRAWLER"

        # 타이어식
        EXC_TIRE_LE_6 = "EXC_TIRE_LE_6"  # 03W 5~6 ton
        EXC_TIRE_LE_17 = "EXC_TIRE_LE_17"  # 06W 12~16 ton
        EXC_TIRE_LE_21 = "EXC_TIRE_LE_21"  # 08W 20~22 ton

        # 크롤러식
        EXC_CR_LE_6_5 = "EXC_CR_LE_6_5"  # 5~6 ton 02급
        EXC_CR_LE_16 = "EXC_CR_LE_16"  # 12~16 ton 06급
        EXC_CR_EQ_20 = "EXC_CR_EQ_20"  # 20~22 ton 08급
        EXC_CR_GE_30 = "EXC_CR_GE_30"  # 30~40 ton 10급

        # direct_nara 이관 커맨드가 사용하는 alias
        direct_alias = "direct_nara"
        legacy_alias = "legacy"
        db_alias = direct_alias if direct_alias in connections else legacy_alias

        self.stdout.write(f"Using legacy alias: {db_alias}")

        eq_qs = (
            Equipment.objects.filter(equipment_type="excavator", legacy_listing_id__isnull=False)
            .only("id", "legacy_listing_id", "sub_type", "weight_class")
            .order_by("id")
        )
        if limit:
            eq_qs = eq_qs[:limit]

        eqs = list(eq_qs)
        self.stdout.write(f"대상 Equipment: {len(eqs)}")

        uid_list = [int(e.legacy_listing_id) for e in eqs]
        uid_to_eq = {int(e.legacy_listing_id): e for e in eqs}

        if not uid_list:
            self.stdout.write("대상이 없습니다.")
            return

        # bulk IN 조회를 위한 chunk
        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        updated = 0
        skipped_no_match = 0

        with transaction.atomic():
            for part in chunks(uid_list, 500):
                placeholders = ",".join(["%s"] * len(part))
                sql = f"""
                    SELECT
                        uid,
                        cate1,
                        (model LIKE CONCAT(CHAR(37), '03W', CHAR(37))) AS has_03W,
                        (model LIKE CONCAT(CHAR(37), '06W', CHAR(37))) AS has_06W,
                        (model LIKE CONCAT(CHAR(37), '08W', CHAR(37))) AS has_08W,
                        (content LIKE CONCAT(CHAR(37), '02급', CHAR(37))) AS has_02g,
                        (content LIKE CONCAT(CHAR(37), '06급', CHAR(37))) AS has_06g,
                        (content LIKE CONCAT(CHAR(37), '08급', CHAR(37))) AS has_08g,
                        (content LIKE CONCAT(CHAR(37), '10급', CHAR(37))) AS has_10g
                    FROM tb_pro
                    WHERE uid IN ({placeholders})
                """
                with connections[db_alias].cursor() as cur:
                    cur.execute(sql, part)
                    rows = cur.fetchall()

                for (
                    uid,
                    cate1,
                    has_03W,
                    has_06W,
                    has_08W,
                    has_02g,
                    has_06g,
                    has_08g,
                    has_10g,
                ) in rows:
                    eq = uid_to_eq.get(int(uid))
                    if not eq:
                        continue

                    # cate1 기준으로 타이어/크롤러를 분기(기존 데이터에 sub_type 정보가 없어서 최선의 휴리스틱)
                    # - cate1=4 는 크롤러로, 그 외(1,12 등)는 타이어로 가정
                    sub_type = EXC_CRAWLER if str(cate1) == "4" else EXC_TIRE

                    # weight_class 채우기
                    weight_class = ""
                    if sub_type == EXC_TIRE:
                        if has_03W:
                            weight_class = EXC_TIRE_LE_6
                        elif has_06W:
                            weight_class = EXC_TIRE_LE_17
                        elif has_08W:
                            weight_class = EXC_TIRE_LE_21
                        else:
                            # 타이어용 W 토큰이 없는 경우, 크롤러용 grade token(02급/06급/08급)을 fallback으로 사용
                            if has_02g:
                                weight_class = EXC_TIRE_LE_6
                            elif has_06g:
                                weight_class = EXC_TIRE_LE_17
                            elif has_08g:
                                weight_class = EXC_TIRE_LE_21
                    else:
                        # 크롤러식
                        if has_02g:
                            weight_class = EXC_CR_LE_6_5
                        elif has_06g:
                            weight_class = EXC_CR_LE_16
                        elif has_08g:
                            weight_class = EXC_CR_EQ_20
                        elif has_10g:
                            weight_class = EXC_CR_GE_30

                    if not weight_class:
                        skipped_no_match += 1
                        continue

                    # idempotent: 변경이 있으면만 반영
                    if eq.sub_type != sub_type or eq.weight_class != weight_class:
                        if not dry_run:
                            eq.sub_type = sub_type
                            eq.weight_class = weight_class
                            eq.save(update_fields=["sub_type", "weight_class"])
                        updated += 1

        self.stdout.write(f"완료: updated={updated}, skipped_no_match={skipped_no_match}, dry_run={dry_run}")

