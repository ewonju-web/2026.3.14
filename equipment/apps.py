from django.apps import AppConfig


class EquipmentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "equipment"
    verbose_name = "장비/회원 관리"

    def ready(self):
        # --- 강제 한글화 코드 (안전한 위치: AppConfig.ready) ---
        try:
            from django.contrib.auth.models import User, Group
            User._meta.verbose_name = "회원"
            User._meta.verbose_name_plural = "회원(User) 계정 관리"
            Group._meta.verbose_name = "권한 그룹"
            Group._meta.verbose_name_plural = "권한 그룹 관리"
        except Exception:
            pass
        # 소셜/일반 가입 시 Profile 자동 생성
        from . import signals  # noqa: F401
