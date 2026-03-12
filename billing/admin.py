"""
관리자: 요금제, 주문/결제, 프리미엄 노출, 딜러 멤버십, 일별 매출
관리자가 편하게 볼 수 있도록 list_per_page, 필터, 검색, 필드 그룹화 적용.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import number_format
from .models import (
    Product, Order, OrderItem, Payment,
    PremiumPlacement, EquipmentUpgrade, DealerMembership, RevenueDaily,
    ConversionEvent,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'product_type', 'slot_type', 'duration_days', 'price_display', 'is_recurring', 'is_active', 'sort_order')
    list_filter = ('product_type', 'slot_type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('sort_order', 'pk')
    list_per_page = 50
    list_editable = ('is_active', 'sort_order')

    def price_display(self, obj):
        return f"{number_format(obj.price, use_l10n=True)}원" if obj.price is not None else "-"
    price_display.short_description = '판매가'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'unit_price', 'quantity', 'target_content_type', 'target_object_id', 'slot_type', 'starts_at', 'expires_at')
    show_change_link = True


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('pg_provider', 'pg_tid', 'amount', 'status', 'requested_at', 'paid_at')
    show_change_link = True
    max_num = 10


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'status', 'total_amount_display', 'refund_amount', 'refunded_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'user__username', 'user__email')
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ('order_number', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 30
    fieldsets = (
        (None, {'fields': ('order_number', 'user', 'status', 'total_amount', 'admin_memo')}),
        ('환불', {'fields': ('refund_amount', 'refunded_at')}),
    )

    def total_amount_display(self, obj):
        return f"{number_format(obj.total_amount, use_l10n=True)}원" if obj.total_amount is not None else "-"
    total_amount_display.short_description = '총액'


@admin.register(PremiumPlacement)
class PremiumPlacementAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'equipment_link', 'status', 'slot_type', 'slot_no', 'category', 'region_key',
        'paid_at', 'expires_at', 'is_active', 'admin_memo_short', 'created_at',
    )
    list_filter = ('status', 'slot_type', 'is_active', 'category')
    search_fields = ('equipment__model_name', 'equipment__manufacturer', 'category', 'region_key', 'admin_memo')
    date_hierarchy = 'created_at'
    list_editable = ('is_active', 'slot_no')
    readonly_fields = ('refunded_at', 'refund_amount', 'period_adjusted_at', 'created_at')
    list_per_page = 50
    fieldsets = (
        (None, {'fields': ('equipment', 'status', 'slot_type', 'slot_no', 'waitlist_rank', 'category', 'region_key', 'match_keywords')}),
        ('기간', {'fields': ('paid_at', 'starts_at', 'expires_at', 'period_adjusted_at')}),
        ('운영', {'fields': ('is_active', 'admin_memo', 'refunded_at', 'refund_amount')}),
    )

    def equipment_link(self, obj):
        if not obj.equipment_id:
            return "-"
        from django.urls import reverse
        url = reverse('admin:equipment_equipment_change', args=[obj.equipment_id])
        return format_html('<a href="{}">#{}</a> {}', url, obj.equipment_id, obj.equipment.model_name if obj.equipment else '-')
    equipment_link.short_description = '장비'

    def admin_memo_short(self, obj):
        if not obj.admin_memo:
            return ""
        return obj.admin_memo[:30] + "…" if len(obj.admin_memo) > 30 else obj.admin_memo
    admin_memo_short.short_description = '메모'


@admin.register(EquipmentUpgrade)
class EquipmentUpgradeAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'max_images', 'is_highlight', 'bump_at', 'expires_at', 'is_expired_display', 'created_at')
    list_filter = ('is_highlight',)
    search_fields = ('equipment__model_name', 'equipment__manufacturer')
    date_hierarchy = 'expires_at'
    list_per_page = 50
    readonly_fields = ('created_at',)

    def is_expired_display(self, obj):
        from django.utils import timezone
        expired = obj.expires_at and obj.expires_at < timezone.now()
        return format_html('<span style="color:{};">{}</span>', 'red' if expired else 'green', '만료' if expired else '유효')
    is_expired_display.short_description = '유효'


@admin.register(DealerMembership)
class DealerMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'period_start', 'period_end', 'is_auto_renew', 'is_active_display', 'updated_at')
    list_filter = ('is_auto_renew',)
    search_fields = ('user__username', 'user__email')
    date_hierarchy = 'period_end'
    list_per_page = 50

    def is_active_display(self, obj):
        return format_html(
            '<span style="color:{};">{}</span>',
            'green' if obj.is_active else 'red',
            '활성' if obj.is_active else '만료'
        )
    is_active_display.short_description = '상태'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_link', 'pg_provider', 'pg_tid_short', 'amount_display', 'status', 'paid_at', 'requested_at')
    list_filter = ('status', 'pg_provider')
    search_fields = ('pg_tid', 'order__order_number')
    readonly_fields = ('order', 'pg_provider', 'pg_tid', 'amount', 'status', 'requested_at', 'paid_at', 'raw_response', 'admin_memo', 'refund_amount', 'refunded_at')
    date_hierarchy = 'requested_at'
    list_per_page = 50
    fieldsets = (
        (None, {'fields': ('order', 'pg_provider', 'pg_tid', 'amount', 'status')}),
        ('시각', {'fields': ('requested_at', 'paid_at')}),
        ('기타', {'fields': ('admin_memo', 'refund_amount', 'refunded_at', 'raw_response')}),
    )

    def order_link(self, obj):
        if not obj.order_id:
            return "-"
        from django.urls import reverse
        url = reverse('admin:billing_order_change', args=[obj.order_id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = '주문'

    def pg_tid_short(self, obj):
        if not obj.pg_tid:
            return "-"
        return obj.pg_tid[:20] + "…" if len(obj.pg_tid) > 20 else obj.pg_tid
    pg_tid_short.short_description = 'PG 거래ID'

    def amount_display(self, obj):
        return f"{number_format(obj.amount, use_l10n=True)}원" if obj.amount is not None else "-"
    amount_display.short_description = '금액'


@admin.register(RevenueDaily)
class RevenueDailyAdmin(admin.ModelAdmin):
    list_display = ('date', 'product_code', 'order_count', 'amount_sum_display', 'created_at')
    list_filter = ('product_code',)
    date_hierarchy = 'date'
    ordering = ('-date', 'product_code')
    list_per_page = 100

    def amount_sum_display(self, obj):
        return f"{number_format(obj.amount_sum, use_l10n=True)}원" if obj.amount_sum is not None else "-"
    amount_sum_display.short_description = '매출합계'


@admin.register(ConversionEvent)
class ConversionEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_type', 'user', 'session_key_short', 'content_type', 'object_id', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('event_type', 'session_key')
    date_hierarchy = 'created_at'
    readonly_fields = ('event_type', 'user', 'session_key', 'content_type', 'object_id', 'metadata', 'created_at')
    list_per_page = 100

    def session_key_short(self, obj):
        if not obj.session_key:
            return "-"
        return obj.session_key[:16] + "…" if len(obj.session_key) > 16 else obj.session_key
    session_key_short.short_description = '세션'
