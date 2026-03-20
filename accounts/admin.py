from django.contrib import admin
from django.utils import timezone

from .models import MembershipGrade, MemberProfile, Subscription, PaymentHistory


@admin.register(MembershipGrade)
class MembershipGradeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_paid", "max_listings", "sort_order")
    list_editable = ("sort_order",)


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    def member_no_display(self, obj):
        return (obj.phone or "").strip() or obj.user.username

    member_no_display.short_description = "회원번호"

    def user_nickname_display(self, obj):
        """
        관리자 목록의 "사용자" 컬럼 표시용.
        - 우선 대표자명/상호(이관 데이터의 이름) 사용
        - 비어 있으면 User.first_name
        - 그래도 없으면 User.username(로그인 아이디)
        """
        return (
            (obj.ceo_name or "").strip()
            or (obj.company_name or "").strip()
            or (getattr(obj.user, "first_name", "") or "").strip()
            or obj.user.username
        )

    user_nickname_display.short_description = "사용자"

    def name_display(self, obj):
        """관리자 목록의 "이름" 컬럼 표시용(대표자명 우선)."""
        name = (obj.ceo_name or "").strip()
        if name:
            return name
        first = (getattr(obj.user, "first_name", None) or "").strip()
        if first:
            return first
        return (obj.user.username or "").strip() or "-"

    name_display.short_description = "이름"

    def joined_display(self, obj):
        d = getattr(obj.user, "date_joined", None)
        return d.strftime("%Y-%m-%d %H:%M") if d else "-"

    joined_display.short_description = "가입일"

    list_display = (
        "member_no_display",
        "user_nickname_display",
        "grade",
        "name_display",
        "phone",
        "joined_display",
        "is_dealer",
        "created_at",
    )
    list_filter = ("grade", "is_dealer")
    search_fields = ("user__username", "user__email", "ceo_name", "company_name", "phone")
    raw_id_fields = ("user",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "plan",
        "started_at",
        "expires_at",
        "status",
        "amount",
        "is_active_display",
    )
    list_filter = ("plan", "status")
    search_fields = ("member__user__username", "pg_uid")
    raw_id_fields = ("member",)

    def is_active_display(self, obj):
        return obj.is_active

    is_active_display.boolean = True
    is_active_display.short_description = "유효"


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ("member", "amount", "pg_provider", "status", "paid_at", "created_at")
    list_filter = ("status",)
    search_fields = ("member__user__username", "pg_uid")
    raw_id_fields = ("member", "subscription")
