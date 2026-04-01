# 유료 회원 노출용: 첫화면 로테이션·우측 배너
from django.db import models
from django.utils import timezone

from .models import Equipment, Profile


def _premium_user_ids():
    today = timezone.now().date()
    return set(
        Profile.objects.filter(is_premium=True)
        .filter(
            models.Q(premium_until__isnull=True) | models.Q(premium_until__gte=today)
        )
        .values_list("user_id", flat=True)
    )


def get_premium_equipment_rotation(limit=18, equipment_type: str | None = None):
    """첫 화면 로테이션용: 유료 회원 매물 중 노출 중인 것, 최신순 후 limit개 (캐러셀 슬라이드 여러 장)."""
    uids = _premium_user_ids()
    if not uids:
        return []
    qs = (
        Equipment.objects.visible()
        .filter(author_id__in=uids, is_sold=False)
    )
    if equipment_type:
        qs = qs.filter(equipment_type=equipment_type)
    return list(qs.order_by("-created_at")[:limit])


def get_premium_user_ids():
    """유료 회원(기간 유효) user id 목록."""
    return list(_premium_user_ids())


def get_premium_equipment_sidebar(limit=6, equipment_type: str | None = None):
    """우측 고정 배너용: 유료 회원 매물 명함, limit개 (로테이션과 구분해 순서 다르게)."""
    uids = _premium_user_ids()
    if not uids:
        return []
    qs = (
        Equipment.objects.visible()
        .filter(author_id__in=uids, is_sold=False)
    )
    if equipment_type:
        qs = qs.filter(equipment_type=equipment_type)
    return list(qs.order_by("?")[:limit])  # 랜덤


def pad_premium_sidebar_slots(items, limit=6):
    """우측 유료 사이드바를 항상 limit칸으로 맞춤. 부족한 칸은 None(빈 카드)."""
    items = list(items)[:limit]
    return items + [None] * (limit - len(items))


def is_user_premium(user):
    """해당 사용자가 현재 유료 회원인지."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = getattr(user, "profile", None)
        if profile and hasattr(profile, "is_premium_active"):
            return profile.is_premium_active
    except Exception:
        pass
    return False


def get_free_listing_count(user):
    """
    무료 한도 계산용: 이번 달(당월)에 해당 사용자가 등록한 장비 매물 수.
    삭제한 것도 포함 — 한 달에 10건까지만 등록 가능, 다음 달에 초기화.
    """
    if not user or not user.is_authenticated:
        return 0
    now = timezone.now()
    return Equipment.objects.filter(
        author=user,
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()


FREE_LISTING_LIMIT = 10  # 무료 회원 한 달 매물 10건까지
