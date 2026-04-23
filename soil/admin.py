from django.contrib import admin
from .models import SoilPost


@admin.register(SoilPost)
class SoilPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'post_type', 'material_type', 'title', 'location', 'quantity', 'contact', 'author', 'created_at', 'is_active')
    list_filter = ('material_type', 'post_type', 'is_active')
    search_fields = ('title', 'location', 'contact', 'note', 'description')
    date_hierarchy = 'created_at'
    list_editable = ('is_active',)
