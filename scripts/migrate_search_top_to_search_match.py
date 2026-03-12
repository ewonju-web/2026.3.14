#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SEARCH_TOP → SEARCH_MATCH 데이터 마이그레이션 (1회 실행)

⚠️ 테스트 서버에서만 사용 권장. 운영/본배포는 Data migration 또는 Management command 사용.
⚠️ Billing 모델에서 SEARCH_TOP enum을 제거했으면, DB에 SEARCH_TOP 문자열이 남아 있을 때
   관리자/조회에서 에러가 날 수 있으므로, 이 스크립트는 **배포 직전 또는 직후** 반드시 1회 실행.

실행 방법 (프로젝트 루트에서):
  python manage.py shell < scripts/migrate_search_top_to_search_match.py
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection, transaction, models

from billing.models import PremiumPlacement
from billing.services.region import normalize_region_key


# 실행 전 상태
before_top = PremiumPlacement.objects.filter(slot_type='SEARCH_TOP').count()
before_match = PremiumPlacement.objects.filter(slot_type='SEARCH_MATCH').count()
print(f"[BEFORE] SEARCH_TOP={before_top}, SEARCH_MATCH={before_match}")

# 1) SEARCH_TOP -> SEARCH_MATCH (raw SQL, 1회, 트랜잭션으로 롤백 가능)
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE billing_premiumplacement "
            "SET slot_type = 'SEARCH_MATCH' "
            "WHERE slot_type = 'SEARCH_TOP'"
        )
        updated = cursor.rowcount

print(f"Updated {updated} PremiumPlacement(s) from SEARCH_TOP to SEARCH_MATCH.")

# 2) category/region_key 비어 있는 것만 대상으로 채우기 (정규화 적용, bulk_update)
qs = PremiumPlacement.objects.filter(slot_type='SEARCH_MATCH').filter(
    models.Q(category__isnull=True) | models.Q(category='') |
    models.Q(region_key__isnull=True) | models.Q(region_key='')
).select_related('equipment')

to_update = []
for p in qs:
    changed = False

    if not p.category:
        # NOTE: 현재는 excavator 단일 카테고리 전제. 멀티 카테고리 도입 시 equipment 기반 매핑 필요.
        p.category = 'excavator'
        changed = True

    if (not p.region_key) and p.equipment_id and getattr(p.equipment, 'current_location', None):
        p.region_key = normalize_region_key(p.equipment.current_location)
        changed = True

    if changed:
        to_update.append(p)

if to_update:
    with transaction.atomic():
        PremiumPlacement.objects.bulk_update(to_update, ['category', 'region_key'], batch_size=1000)

print(f"Filled category/region_key for {len(to_update)} placement(s).")

# 실행 후 상태
after_top = PremiumPlacement.objects.filter(slot_type='SEARCH_TOP').count()
after_match = PremiumPlacement.objects.filter(slot_type='SEARCH_MATCH').count()
empty_cat = PremiumPlacement.objects.filter(slot_type='SEARCH_MATCH').filter(
    models.Q(category__isnull=True) | models.Q(category='')
).count()
empty_region = PremiumPlacement.objects.filter(slot_type='SEARCH_MATCH').filter(
    models.Q(region_key__isnull=True) | models.Q(region_key='')
).count()

print(f"[AFTER] SEARCH_TOP={after_top}, SEARCH_MATCH={after_match}")
print(f"[AFTER] empty category={empty_cat}, empty region_key={empty_region}")
print("Done.")
