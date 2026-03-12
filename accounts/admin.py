from django.contrib import admin
from django.utils import timezone

from .models import MembershipGrade, MemberProfile, Subscription, PaymentHistory


@admin.register(MembershipGrade)
class MembershipGradeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_paid", "max_listings", "sort_order")
    list_editable = ("sort_order",)


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "grade",
        "company_name",
        "phone",
        "is_dealer",
        "created_at",
    )
    list_filter = ("grade", "is_dealer")
    search_fields = ("user__username", "user__email", "company_name", "phone")
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
