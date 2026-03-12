# Billing (유료화) 앱

굴삭기나라 프리미엄 상단 노출, 판매글 업그레이드, 딜러 PRO 멤버십을 위한 DB 및 서비스 레이어입니다.

## 설치

1. `config/settings.py`의 `INSTALLED_APPS`에 `'billing'` 추가 (equipment 다음 권장).
2. `python manage.py makemigrations billing && python manage.py migrate`

## 모델 요약

| 모델 | 용도 |
|------|------|
| Product | 요금제 마스터 (상단노출 7일/30일, 업그레이드, PRO 월정액 등) |
| Order / OrderItem | 주문 및 주문 항목 (어떤 상품을 어떤 매물/사용자에 적용했는지) |
| Payment | PG 결제 기록 |
| PremiumPlacement | 프리미엄 상단 노출 슬롯 (카테고리/지역/검색) |
| EquipmentUpgrade | 매물 업그레이드 (사진 20장, 강조, 재노출) |
| DealerMembership | 딜러 PRO 구독 (기간, 자동갱신) |
| RevenueDaily | 일별 매출 집계 (크론으로 채움) |

## 노출 순서

`billing.services.exposure_ordering`:

- `filter_premium_top_equipment_ids(slot_type, category=..., region_key=...)` → 해당 슬롯의 상단 노출 매물 ID 리스트.
- `get_ordered_equipment_ids(equipment_queryset, slot_type, ...)` → 프리미엄 ID 먼저, 나머지 최신순 ID 리스트.

목록 뷰에서 위 ID 순서로 매물을 보여주면 됩니다.

## 상세 기획

`docs/MONETIZATION_PLAN.md` 참고.
