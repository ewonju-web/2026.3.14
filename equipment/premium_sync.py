"""
매물/첫화면 유료 노출용 equipment.Profile 동기화.
accounts 구독·결제 및 billing 딜러 멤버십과 연동한다.
"""
from __future__ import annotations

from datetime import date

from django.utils import timezone

from .models import Profile


def set_equipment_premium_until(user, premium_until: date | None) -> None:
    """
    유료 노출 기간 설정. premium_until 이 오늘 이전이면 유료 해제.
    None 이면 만료일 없음(기존 is_premium_active 규칙과 동일).
    """
    if not user or not getattr(user, "pk", None):
        return
    profile, _ = Profile.objects.get_or_create(
        user=user,
        defaults={"user_type": Profile.USER_TYPE_CHOICES[0][0]},
    )
    today = timezone.now().date()
    if premium_until is not None and premium_until < today:
        profile.is_premium = False
        profile.premium_until = premium_until
    else:
        profile.is_premium = True
        profile.premium_until = premium_until
    profile.save(update_fields=["is_premium", "premium_until"])


def clear_equipment_premium(user) -> None:
    if not user or not getattr(user, "pk", None):
        return
    Profile.objects.filter(user=user).update(is_premium=False, premium_until=None)


def refresh_equipment_premium_for_user(user) -> None:
    """
    accounts.Subscription(활성) + billing.DealerMembership(유효) 중 가장 늦은 만료일을 반영.
    둘 다 없으면 equipment.Profile 유료 해제.
    """
    if not user or not getattr(user, "pk", None):
        return

    best: date | None = None

    try:
        from accounts.models import MemberProfile, Subscription

        mp = MemberProfile.objects.filter(user_id=user.pk).first()
        if mp:
            sub = (
                mp.subscriptions.filter(
                    status=Subscription.STATUS_ACTIVE,
                    expires_at__gte=timezone.now(),
                )
                .order_by("-expires_at")
                .first()
            )
            if sub:
                best = sub.expires_at.date()
    except Exception:
        pass

    try:
        from billing.models import DealerMembership

        dm = DealerMembership.objects.filter(user_id=user.pk).first()
        if dm and dm.is_active:
            if best is None or dm.period_end > best:
                best = dm.period_end
    except Exception:
        pass

    if best is not None and best >= timezone.now().date():
        set_equipment_premium_until(user, best)
    else:
        clear_equipment_premium(user)
