from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['sender', 'content', 'is_filtered', 'is_read', 'created_at']
    fields = ['sender', 'content', 'is_filtered', 'is_read', 'created_at']
    ordering = ['-created_at']
    max_num = 20


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation_type', 'activity', 'participant_count', 'last_message_at', 'created_at']
    list_filter = ['conversation_type', 'created_at']
    search_fields = ['participants__email', 'activity__title']
    filter_horizontal = ['participants']
    inlines = [MessageInline]
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Katılımcı Sayısı'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sender', 'conversation', 'content_preview', 'is_filtered', 'is_read', 'created_at']
    list_filter = ['is_filtered', 'is_read', 'created_at']
    search_fields = ['content', 'sender__email']
    date_hierarchy = 'created_at'
    readonly_fields = ['original_content']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'İçerik'
