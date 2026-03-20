from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.formats import number_format
from django.db.models import Count, Q
from django.utils import timezone
from .models import Equipment, EquipmentImage, Profile, JobPost, Part, PartImage, PartsShop, EquipmentFavorite, PartFavorite, Comment, DeletedListingLog


# 1. 매물 관리
class EquipmentImageInline(admin.TabularInline):
    model = EquipmentImage
    extra = 1
    show_change_link = True


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'equipment_type', 'model_name', 'manufacturer', 'year_manufactured', 'listing_price_display',
        'current_location', 'vehicle_number', 'listing_status', 'is_sold', 'author', 'last_bumped_at', 'created_at',
    ]
    list_filter = ('equipment_type', 'listing_status', 'is_sold', 'manufacturer')
    search_fields = ('model_name', 'manufacturer', 'current_location', 'description')
    date_hierarchy = 'created_at'
    list_per_page = 50
    inlines = [EquipmentImageInline]
    list_editable = ('listing_status', 'is_sold')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {'fields': ('author', 'equipment_type', 'model_name', 'manufacturer', 'year_manufactured', 'month_manufactured', 'operating_hours')}),
        ('가격·위치·차량번호', {'fields': ('listing_price', 'current_location', 'vehicle_number', 'description')}),
        ('상태', {'fields': ('listing_status', 'is_sold', 'password', 'created_at')}),
    )

    def listing_price_display(self, obj):
        if obj.listing_price is None:
            return "-"
        return f"{number_format(obj.listing_price, use_l10n=True)}원"
    listing_price_display.short_description = '판매가'


# 2. 부품 관리 (사진 포함)
class PartImageInline(admin.TabularInline):
    model = PartImage
    extra = 3
    show_change_link = True


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['category', 'title', 'price', 'location', 'author', 'created_at']
    list_filter = ('category', 'created_at')
    search_fields = ('title', 'location', 'compatibility', 'description')
    date_hierarchy = 'created_at'
    list_per_page = 50
    inlines = [PartImageInline]


@admin.register(PartsShop)
class PartsShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'region', 'contact', 'address', 'created_at']
    list_filter = ('region',)
    search_fields = ['name', 'region', 'address', 'note']
    list_per_page = 50


# 3. 구인구직 및 프로필
@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = ['id', 'job_type', 'title', 'company_name', 'region_sido', 'region_sigungu', 'recruit_count', 'deadline_type', 'deadline', 'author', 'created_at']
    list_filter = ('job_type', 'region_sido', 'created_at')
    search_fields = ('title', 'location', 'region_sido', 'region_sigungu', 'content', 'writer_display')
    date_hierarchy = 'created_at'
    list_per_page = 50


# --- 회원(Profile) 목록: 기존/신규, 인증, 개인·사업자, 무료·유료, 매물수, 결제이력, 신고 ---
class MemberTypeFilter(admin.SimpleListFilter):
    title = '회원 구분'
    parameter_name = 'member_type'
    def lookups(self, request, model_admin):
        return [('legacy', '기존회원'), ('new', '신규회원')]
    def queryset(self, request, queryset):
        if self.value() == 'legacy':
            return queryset.exclude(legacy_member_id__isnull=True)
        if self.value() == 'new':
            return queryset.filter(legacy_member_id__isnull=True)
        return queryset


class PremiumStatusFilter(admin.SimpleListFilter):
    title = '요금 구분'
    parameter_name = 'premium'
    def lookups(self, request, model_admin):
        return [('free', '무료'), ('paid', '유료')]
    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'free':
            return queryset.filter(
                Q(is_premium=False) | Q(is_premium=True, premium_until__lt=today)
            )
        if self.value() == 'paid':
            return queryset.filter(
                is_premium=True
            ).filter(Q(premium_until__isnull=True) | Q(premium_until__gte=today))
        return queryset


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        'member_number_display', 'user_nickname_display', 'name_display', 'phone',
        'premium_display', 'premium_until', 'premium_remaining_display',
        'payment_memo_display',
        'equipment_count_display', 'member_type_display', 'verified_display', 'user_type_display',
        'is_premium', 'payment_count_display', 'company_name', 'is_approved', 'created_display',
    ]
    list_filter = (MemberTypeFilter, 'phone_verified', 'user_type', PremiumStatusFilter, 'is_approved')
    search_fields = ('user__username', 'user__first_name', 'user__email', 'company_name', 'phone')
    list_per_page = 50
    list_editable = ('is_premium',)
    readonly_fields = ('equipment_count_display', 'payment_count_display', 'reported_display', 'created_display')
    date_hierarchy = 'user__date_joined'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user').annotate(_equipment_count=Count('user__authored_equipment', distinct=True))

    def name_display(self, obj):
        """이름: User.first_name 또는 상호명."""
        if not obj.user_id:
            return '-'
        name = (getattr(obj.user, 'first_name', None) or '').strip()
        if name:
            return name
        # accounts.MemberProfile에 이름이 들어있는 회원 fallback
        try:
            mp_name = (getattr(obj.user, 'member_profile', None).ceo_name or '').strip()
            if mp_name:
                return mp_name
        except Exception:
            pass
        if (getattr(obj, 'company_name', None) or '').strip():
            return obj.company_name.strip()
        # 최후 fallback: 화면에서 "빈칸"처럼 보이지 않게 로그인 아이디라도 표시
        return (getattr(obj.user, 'username', None) or '').strip() or '-'
    name_display.short_description = '이름'

    def user_nickname_display(self, obj):
        """관리자 목록에서 '사용자'는 로그인 아이디 대신 닉네임(이름)을 보여줌."""
        if not obj.user_id:
            return '-'
        first = (getattr(obj.user, 'first_name', None) or '').strip()
        if first:
            return first
        # MemberProfile에 값이 있는 경우 우선
        try:
            mp_ceo = (getattr(obj.user, 'member_profile', None).ceo_name or '').strip()
            if mp_ceo:
                return mp_ceo
        except Exception:
            pass
        if (getattr(obj, 'company_name', None) or '').strip():
            return obj.company_name.strip()
        # User.last_name은 "닉네임"으로 쓰는 편이어서 이름 표시 용 fallback으로도 활용
        last = (getattr(obj.user, 'last_name', None) or '').strip()
        if last:
            return last
        return obj.user.username or '-'

    user_nickname_display.short_description = '사용자'

    def member_number_display(self, obj):
        """회원번호: 전화번호 우선 표시."""
        ph = (getattr(obj, 'phone', None) or '').strip()
        if ph:
            return ph
        username = (getattr(obj.user, 'username', None) or '').strip() if getattr(obj, 'user_id', None) else ''
        return username or '-'

    member_number_display.short_description = '회원번호'

    def member_type_display(self, obj):
        if obj.legacy_member_id is not None:
            return format_html('<span style="color:#059669;">기존</span>')
        if getattr(obj.user, 'username', '').startswith('legacy_'):
            return format_html('<span style="color:#059669;">기존</span>')
        return format_html('<span style="color:#6b7280;">신규</span>')
    member_type_display.short_description = '구분'

    def verified_display(self, obj):
        if getattr(obj, 'phone_verified', False):
            return format_html('<span style="color:#059669;">O</span>')
        return format_html('<span style="color:#dc2626;">X</span>')
    verified_display.short_description = '인증'

    def user_type_display(self, obj):
        return obj.get_user_type_display() if obj.user_type else '-'
    user_type_display.short_description = '개인/사업자'

    def premium_display(self, obj):
        """현재 유료 상태."""
        if not getattr(obj, 'is_premium', False):
            return format_html('<span>무료</span>')
        today = timezone.now().date()
        if obj.premium_until and obj.premium_until < today:
            return format_html('<span style="color:#9ca3af;">만료</span>')
        return format_html('<span style="color:#d97706; font-weight:bold;">유료</span>')
    premium_display.short_description = '유료 상태'

    def premium_remaining_display(self, obj):
        """남은 기간: D-day, 무기한, 만료, -."""
        if not getattr(obj, 'is_premium', False):
            return '-'
        if not obj.premium_until:
            return format_html('<span style="color:#059669;">무기한</span>')
        today = timezone.now().date()
        if obj.premium_until < today:
            return format_html('<span style="color:#9ca3af;">만료</span>')
        delta = (obj.premium_until - today).days
        if delta == 0:
            return 'D-0'
        return f'D-{delta}'
    premium_remaining_display.short_description = '남은 기간'

    def payment_memo_display(self, obj):
        """최근 결제 여부 또는 메모: 마지막 결제완료 주문의 결제일·메모."""
        try:
            from billing.models import Order
            last_order = Order.objects.filter(user_id=obj.user_id, status='PAID').order_by('-updated_at').first()
            if not last_order:
                return format_html('<span style="color:#9ca3af;">결제 없음</span>')
            parts = []
            last_payment = getattr(last_order, 'payments', None)
            if last_payment:
                paid = last_payment.filter(status='SUCCESS').order_by('-paid_at').first()
                if paid and getattr(paid, 'paid_at', None):
                    parts.append(paid.paid_at.strftime('%Y-%m-%d'))
            if not parts and getattr(last_order, 'updated_at', None):
                parts.append(last_order.updated_at.strftime('%Y-%m-%d'))
            memo = (getattr(last_order, 'admin_memo', None) or '').strip()
            if memo:
                parts.append(memo[:25] + '…' if len(memo) > 25 else memo)
            return ' · '.join(parts) if parts else '결제 O'
        except Exception:
            return '-'
    payment_memo_display.short_description = '최근 결제/메모'

    def equipment_count_display(self, obj):
        if hasattr(obj, '_equipment_count'):
            return obj._equipment_count
        return getattr(obj.user, 'authored_equipment', []).count() if obj.user_id else 0
    equipment_count_display.short_description = '매물 수'

    def payment_count_display(self, obj):
        try:
            from billing.models import Order
            cnt = Order.objects.filter(user_id=obj.user_id, status='PAID').count()
            return f'{cnt}건' if cnt else '-'
        except Exception:
            return '-'
    payment_count_display.short_description = '결제 이력'

    def reported_display(self, obj):
        return '없음'
    reported_display.short_description = '신고'

    def created_display(self, obj):
        if not obj.user_id:
            return '-'
        try:
            d = obj.user.date_joined
            return d.strftime('%Y-%m-%d %H:%M') if d else '-'
        except Exception:
            return '-'
    created_display.short_description = '가입일'


@admin.register(EquipmentFavorite)
class EquipmentFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'equipment', 'created_at']
    list_filter = ('created_at',)
    search_fields = ('user__username', 'equipment__model_name')
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(PartFavorite)
class PartFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'part', 'created_at']
    list_filter = ('created_at',)
    search_fields = ('user__username', 'part__title')
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'author', 'author_name', 'content_type', 'object_id', 'content_short', 'created_at']
    list_filter = ('content_type', 'created_at')
    search_fields = ('content', 'author_name', 'author__username')
    date_hierarchy = 'created_at'
    list_per_page = 50
    readonly_fields = ('created_at',)

    def content_short(self, obj):
        if not obj.content:
            return ""
        return obj.content[:40] + "…" if len(obj.content) > 40 else obj.content
    content_short.short_description = '내용'


@admin.register(DeletedListingLog)
class DeletedListingLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'model_name', 'image_hash', 'deleted_at')
    list_filter = ('deleted_at',)
    search_fields = ('user__username', 'model_name')
    date_hierarchy = 'deleted_at'
    readonly_fields = ('deleted_at',)


class CustomAuthUserAdmin(DjangoUserAdmin):
    """auth.User 목록을 리뉴얼 회원 관리 용도에 맞춰 단순 표시."""
    list_display = (
        "member_no_display",
        "username",
        "name_display",
        "joined_display",
        "is_staff",
    )
    search_fields = ("username", "first_name", "profile__phone")
    ordering = ("-date_joined",)

    def member_no_display(self, obj):
        # 회원번호는 전화번호 우선(없으면 username 사용)
        try:
            ph = (getattr(obj, "profile", None).phone or "").strip()
        except Exception:
            ph = ""
        return ph or obj.username

    member_no_display.short_description = "전화번호"

    def name_display(self, obj):
        return (obj.first_name or "").strip() or "-"

    name_display.short_description = "이름"

    def joined_display(self, obj):
        d = getattr(obj, "date_joined", None)
        return d.strftime("%Y-%m-%d %H:%M") if d else "-"

    joined_display.short_description = "가입일"


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomAuthUserAdmin)
