from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import number_format
from .models import Equipment, EquipmentImage, Profile, JobPost, Part, PartImage, PartsShop, EquipmentFavorite, PartFavorite, Comment


# 1. 매물 관리
class EquipmentImageInline(admin.TabularInline):
    model = EquipmentImage
    extra = 1
    show_change_link = True


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'equipment_type', 'model_name', 'manufacturer', 'year_manufactured', 'listing_price_display',
        'current_location', 'vehicle_number', 'listing_status', 'is_sold', 'author', 'created_at',
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


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'user_type', 'company_name', 'phone', 'is_approved', 'business_number']
    list_filter = ('user_type', 'is_approved')
    search_fields = ('user__username', 'user__email', 'company_name', 'phone')
    list_per_page = 50


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
