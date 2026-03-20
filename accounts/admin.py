from django.contrib import admin
from django.utils import timezone

from .models import MembershipGrade, MemberProfile, Subscription, PaymentHistory


@admin.register(MembershipGrade)
class MembershipGradeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_paid", "max_listings", "sort_order")
    list_editable = ("sort_order",)


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    def _looks_like_phone_number(self, raw: str) -> bool:
        if not raw:
            return False
        digits = "".join(ch for ch in str(raw) if ch.isdigit())
        # 일반적인 010/휴대폰 형태만 대략 판정 (admin 표시용 폴백 방지)
        return (digits.startswith("010") and len(digits) == 11) or (digits.startswith("0") and len(digits) in (10, 11))

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
        # 로그인 아이디(username)가 전화번호 형태였던 이력이 있어서,
        # name 컬럼은 username 폴백을 제거(전화번호가 이름으로 보이는 문제 방지).
        name = (obj.ceo_name or "").strip()
        if name and not self._looks_like_phone_number(name):
            return name

        # company_name이 대표명 역할을 하는 경우가 많아서 우선순위에 포함
        company = (obj.company_name or "").strip()
        if company and not self._looks_like_phone_number(company):
            return company

        first = (getattr(obj.user, "first_name", None) or "").strip()
        if first and not self._looks_like_phone_number(first):
            return first

        return "-"

    name_display.short_description = "이름"

    def joined_display(self, obj):
        d = getattr(obj.user, "date_joined", None)
        return d.strftime("%Y-%m-%d %H:%M") if d else "-"

    joined_display.short_description = "가입일"

    list_display = (
        "member_no_display",
        "name_display",
        "phone",
        "joined_display",
    )
    list_filter = ()
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
