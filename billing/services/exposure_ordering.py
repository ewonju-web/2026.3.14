"""
노출 우선순위 로직 V2 (개선안 반영)

- 프리미엄: paid_at ASC (먼저 결제한 사람 우선, 공정)
- 카테고리 TOP: 고정 5칸(slot_no 1~5) + 대기열
- SEARCH_MATCH: 카테고리/지역(필수) + 키워드 매칭 시에만 상단 노출
- bump: 최대 1~3개만 섞기 (별도 섹션 또는 목록 상단 1~3개)
"""
from django.utils import timezone

from billing.models import PremiumPlacement, PlacementStatus, SlotType


def get_category_top_equipment_ids(category: str, slot_count: int = 5) -> list[int]:
    """
    카테고리 TOP 고정 슬롯(1~5) + 대기열. 정렬은 paid_at ASC(공정).
    슬롯이 비었으면 대기열에서 paid_at ASC 1건씩 채움.
    """
    now = timezone.now()
    # 1~5 슬롯 보유 중인 활성 건 (status=ACTIVE, 환불 제외)
    filled = PremiumPlacement.objects.filter(
        slot_type=SlotType.CATEGORY_TOP,
        category=category,
        status=PlacementStatus.ACTIVE,
        is_active=True,
        expires_at__gte=now,
        refunded_at__isnull=True,
        slot_no__isnull=False,
    ).order_by('slot_no').values_list('slot_no', 'equipment_id')
    slot_to_equipment = {s: eid for s, eid in filled}

    # 비어 있는 슬롯 번호에 대기열(status=WAITING)에서 paid_at ASC로 채움
    used_ids = set(slot_to_equipment.values())
    waitlist = (
        PremiumPlacement.objects.filter(
            slot_type=SlotType.CATEGORY_TOP,
            category=category,
            status=PlacementStatus.WAITING,
            is_active=True,
            refunded_at__isnull=True,
            slot_no__isnull=True,
        )
        .exclude(equipment_id__in=used_ids)
        .order_by('paid_at', 'id')  # 공정 정렬(paid_at ASC), 분쟁 방지용 id
        .values_list('equipment_id', flat=True)
    )
    waitlist_ids = list(waitlist)[: slot_count - len(slot_to_equipment)]
    for i, eid in enumerate(waitlist_ids):
        for slot_no in range(1, slot_count + 1):
            if slot_no not in slot_to_equipment:
                slot_to_equipment[slot_no] = eid
                break

    return [slot_to_equipment.get(s) for s in range(1, slot_count + 1) if slot_to_equipment.get(s)]


def get_region_top_equipment_ids(region_key: str, limit: int = 5) -> list[int]:
    """지역 TOP. paid_at ASC 공정 정렬."""
    now = timezone.now()
    return list(
        PremiumPlacement.objects.filter(
            slot_type=SlotType.REGION_TOP,
            region_key=region_key,
            status=PlacementStatus.ACTIVE,
            is_active=True,
            expires_at__gte=now,
            refunded_at__isnull=True,
        )
        .order_by('paid_at', 'id')  # 공정 정렬(paid_at ASC)
        .values_list('equipment_id', flat=True)[:limit]
    )


def get_search_match_equipment_ids(
    category: str | None,
    region_key: str | None,
    search_keywords: list[str] | None = None,
    limit: int = 5,
) -> list[int]:
    """
    SEARCH_MATCH: 카테고리/지역(필수) 조건 + 키워드 매칭 시에만 상단 노출.
    무조건 노출(SEARCH_TOP) 금지.
    """
    now = timezone.now()
    qs = PremiumPlacement.objects.filter(
        slot_type=SlotType.SEARCH_MATCH,
        status=PlacementStatus.ACTIVE,
        is_active=True,
        expires_at__gte=now,
        refunded_at__isnull=True,
    )
    if category:
        qs = qs.filter(category=category)
    if region_key:
        qs = qs.filter(region_key=region_key)
    qs = qs.order_by('paid_at', 'id')  # 공정 정렬(paid_at ASC)
    # match_keywords: {"raw": [...], "norm": [...]} 형식 권장. norm 기준 매칭. 리스트(레거시)도 허용.
    if search_keywords:
        clean_kw = set(k for k in search_keywords if k)
        if clean_kw:
            out = []
            for eid, kw in qs.values_list('equipment_id', 'match_keywords')[: limit * 3]:
                norm_list = []
                if isinstance(kw, dict) and kw:
                    norm_list = kw.get('norm') or []
                elif isinstance(kw, list):
                    norm_list = kw
                if not norm_list or (clean_kw & set(norm_list)):
                    out.append(eid)
                    if len(out) >= limit:
                        break
            return out
    return list(qs.values_list('equipment_id', flat=True)[:limit])


def get_bump_equipment_ids(limit: int = 3, bump_hours: int = 24) -> list[int]:
    """
    업그레이드 bump: 전체 정렬 오염 방지 위해 최대 1~3개만.
    bump_at이 최근 bump_hours 이내인 것만. 별도 섹션 또는 목록 상단에만 삽입.
    """
    from billing.models import EquipmentUpgrade
    from datetime import timedelta
    threshold = timezone.now() - timedelta(hours=bump_hours)
    return list(
        EquipmentUpgrade.objects.filter(
            expires_at__gte=timezone.now(),
            bump_at__gte=threshold,
        )
        .order_by('-bump_at')
        .values_list('equipment_id', flat=True)[:limit]
    )


def merge_list_with_bump(main_equipment_ids: list[int], bump_ids: list[int], max_bump: int = 3) -> list[int]:
    """
    목록에 bump를 1~3개만 섞기. main 앞에 bump 최대 max_bump개 삽입 후 나머지 main.
    """
    bump_ids = [eid for eid in bump_ids if eid not in main_equipment_ids][:max_bump]
    main_ids = [eid for eid in main_equipment_ids if eid not in bump_ids]
    return bump_ids + main_ids
