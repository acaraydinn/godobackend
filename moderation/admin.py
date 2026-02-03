from django.contrib import admin
from .models import ReportedContent, BannedWord, ModerationLog


@admin.register(ReportedContent)
class ReportedContentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'reporter', 'report_type', 'reason', 'status', 
        'reviewed_by', 'created_at'
    ]
    list_filter = ['report_type', 'reason', 'status', 'created_at']
    search_fields = [
        'reporter__email', 'reported_user__email', 
        'description', 'admin_notes'
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Şikayet Bilgileri', {
            'fields': ('reporter', 'report_type', 'reason', 'description')
        }),
        ('Hedef', {
            'fields': ('reported_user', 'reported_activity', 'reported_message')
        }),
        ('Durum', {
            'fields': ('status', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Tarihler', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['mark_reviewed', 'mark_action_taken', 'mark_dismissed']
    
    def mark_reviewed(self, request, queryset):
        queryset.update(status='reviewed', reviewed_by=request.user)
    mark_reviewed.short_description = 'İncelendi olarak işaretle'
    
    def mark_action_taken(self, request, queryset):
        queryset.update(status='action_taken', reviewed_by=request.user)
    mark_action_taken.short_description = 'İşlem yapıldı olarak işaretle'
    
    def mark_dismissed(self, request, queryset):
        queryset.update(status='dismissed', reviewed_by=request.user)
    mark_dismissed.short_description = 'Reddedildi olarak işaretle'


@admin.register(BannedWord)
class BannedWordAdmin(admin.ModelAdmin):
    list_display = ['word', 'is_regex', 'is_active', 'created_at']
    list_filter = ['is_regex', 'is_active']
    search_fields = ['word']
    list_editable = ['is_active']


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'moderator', 'target_user', 'action', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['target_user__email', 'moderator__email', 'reason']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at']
