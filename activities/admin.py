from django.contrib import admin
from .models import Activity, ActivityCategory, ActivityParticipation, ActivityImage


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'mode', 'icon', 'order', 'is_active']
    list_filter = ['mode', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'name_en']


class ActivityImageInline(admin.TabularInline):
    model = ActivityImage
    extra = 1


class ActivityParticipationInline(admin.TabularInline):
    model = ActivityParticipation
    extra = 0
    readonly_fields = ['applied_at', 'responded_at']
    fields = ['user', 'status', 'is_group', 'group_member_count', 'applied_at', 'responded_at']


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'creator', 'mode', 'category', 'status',
        'current_participants', 'max_participants', 'start_time', 'is_active'
    ]
    list_filter = ['mode', 'status', 'category', 'is_instant', 'is_public_seo', 'city']
    search_fields = ['title', 'description', 'creator__email', 'creator__display_name']
    date_hierarchy = 'start_time'
    readonly_fields = ['created_at', 'updated_at', 'current_participants']
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('creator', 'title', 'description', 'category', 'mode')
        }),
        ('Konum', {
            'fields': ('latitude', 'longitude', 'address_display', 'address_full', 'city', 'district')
        }),
        ('Zaman', {
            'fields': ('start_time', 'end_time')
        }),
        ('Katılımcılar', {
            'fields': ('max_participants', 'current_participants')
        }),
        ('Sosyal Mod', {
            'fields': ('is_instant', 'is_group_join', 'group_size_min', 'group_size_max'),
            'classes': ('collapse',)
        }),
        ('Profesyonel Mod', {
            'fields': ('company_domain_filter',),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('is_public_seo', 'seo_slug'),
            'classes': ('collapse',)
        }),
        ('Durum', {
            'fields': ('status', 'is_active', 'created_at', 'updated_at')
        }),
    )
    
    inlines = [ActivityImageInline, ActivityParticipationInline]


@admin.register(ActivityParticipation)
class ActivityParticipationAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity', 'status', 'is_group', 'group_member_count', 'applied_at']
    list_filter = ['status', 'is_group']
    search_fields = ['user__email', 'activity__title']
    date_hierarchy = 'applied_at'
    readonly_fields = ['applied_at', 'responded_at']
