from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'trust_score')
    # 어드민 페이지 상단 타이틀 강제 변경
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        model._meta.verbose_name = "회원"
        model._meta.verbose_name_plural = "3. 회원 관리 항목"
