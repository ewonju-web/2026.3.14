from django.contrib import admin
from .models import ChatRoom, ChatMessage


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'equipment', 'soil_post', 'job_post', 'buyer', 'seller', 'created_at', 'last_message_at']
    list_filter = ['created_at']
    search_fields = ['buyer__username', 'seller__username']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'room', 'sender', 'message_short', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']

    def message_short(self, obj):
        return (obj.message[:40] + '...') if len(obj.message) > 40 else obj.message
    message_short.short_description = '메시지'
