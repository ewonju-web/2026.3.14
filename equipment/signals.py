# 소셜/일반 가입 시 equipment.Profile 자동 생성 (휴대폰 인증은 별도 필수)
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=get_user_model())
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
