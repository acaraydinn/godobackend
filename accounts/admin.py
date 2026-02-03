from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from .models import User, BlockedUser, OTP, LegalDocument, UserPhoto, BroadcastNotification
from .notifications import send_notification_to_user, send_notification_to_all


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'display_name', 'current_mode', 'is_verified_company', 'is_active', 'date_joined']
    list_filter = ['current_mode', 'is_verified_company', 'is_active', 'is_staff']
    search_fields = ['email', 'display_name', 'phone']
    ordering = ['-date_joined']
    actions = ['send_notification_to_selected']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profil', {'fields': ('display_name', 'phone', 'avatar', 'bio')}),
        ('Mod Ayarları', {'fields': ('current_mode',)}),
        ('Profesyonel', {'fields': ('github_url', 'linkedin_url', 'portfolio_url', 'skills')}),
        ('Şirket/Kampüs', {'fields': ('is_verified_company', 'company_domain', 'company_name')}),
        ('Güvenlik', {'fields': ('is_2fa_enabled', 'fcm_token')}),
        ('Gizlilik', {'fields': ('privacy_settings', 'data_consent_at', 'terms_accepted_at')}),
        ('İzinler', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Tarihler', {'fields': ('date_joined', 'last_active')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'display_name'),
        }),
    )
    
    readonly_fields = ['date_joined', 'last_active']
    
    @admin.action(description="📢 Seçili kullanıcılara bildirim gönder")
    def send_notification_to_selected(self, request, queryset):
        """Send notification to selected users."""
        total_sent = 0
        for user in queryset:
            result = send_notification_to_user(
                user=user,
                title="📢 GoDo Duyuru",
                body="Yeni güncellemeler var! Uygulamayı açın.",
                data={'type': 'announcement'}
            )
            total_sent += result
        
        self.message_user(
            request,
            f"{total_sent} cihaza bildirim gönderildi ({queryset.count()} kullanıcı seçildi).",
            messages.SUCCESS
        )


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ['blocker', 'blocked', 'created_at']
    list_filter = ['created_at']
    search_fields = ['blocker__email', 'blocked__email']


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['user', 'otp_type', 'is_used', 'expires_at', 'created_at']
    list_filter = ['otp_type', 'is_used']
    search_fields = ['user__email']


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'document_type', 'version', 'is_active', 'updated_at']
    list_filter = ['document_type', 'is_active']
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(UserPhoto)
class UserPhotoAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_primary', 'order', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['user__email', 'user__display_name']
    list_editable = ['is_primary', 'order']
    ordering = ['user', 'order']


# ========== Broadcast Notification Admin ==========

@admin.register(BroadcastNotification)
class BroadcastNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'devices_reached', 'sent_by', 'sent_at']
    readonly_fields = ['sent_at', 'sent_by', 'devices_reached']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only on create
            obj.sent_by = request.user
            # Send the notification
            result = send_notification_to_all(
                title=obj.title,
                body=obj.body,
                data={'type': 'broadcast'}
            )
            obj.devices_reached = result
        super().save_model(request, obj, form, change)
    
    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing sent notifications

