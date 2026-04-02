"""
User(로그인 계정) 생성 시 MemberProfile 자동 생성 + 일반회원 등급 연결
구독/결제 시 equipment.Profile 유료 노출 동기화
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import MemberProfile, MembershipGrade, Subscription, PaymentHistory


@receiver(post_save, sender=get_user_model())
def create_member_profile_on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    if hasattr(instance, "member_profile"):
        return
    grade = MembershipGrade.objects.filter(code="normal").first()
    if not grade:
        return
    MemberProfile.objects.get_or_create(
        user=instance,
        defaults={
            "grade": grade,
            "phone": getattr(instance, "email", "") or "미입력",
        },
    )


def _refresh_equipment_premium(user):
    from equipment.premium_sync import refresh_equipment_premium_for_user

    if user_id := getattr(user, "pk", None):
        transaction.on_commit(
            lambda uid=user_id: refresh_equipment_premium_for_user(
                get_user_model().objects.get(pk=uid)
            )
        )


@receiver(post_save, sender=Subscription)
def sync_equipment_premium_on_subscription(sender, instance, **kwargs):
    """정액제 구독 저장 시 매물 유료 노출 기간 갱신."""
    try:
        user = instance.member.user
    except Exception:
        return
    _refresh_equipment_premium(user)


@receiver(post_save, sender=PaymentHistory)
def sync_equipment_premium_on_payment_history(sender, instance, **kwargs):
    """PG 결제 이력 기록 시(성공) 유료 노출 동기화 — 구독 연동 시 만료일 반영."""
    if instance.status != PaymentHistory.STATUS_SUCCESS:
        return
    try:
        user = instance.member.user
    except Exception:
        return
    _refresh_equipment_premium(user)
