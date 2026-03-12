"""
User(로그인 계정) 생성 시 MemberProfile 자동 생성 + 일반회원 등급 연결
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import MemberProfile, MembershipGrade


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
