"""
URL configuration for GoDo project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from accounts import views as accounts_views

# Customize admin site titles
admin.site.site_header = "GoDo Yönetim Paneli"
admin.site.site_title = "GoDo Admin"
admin.site.index_title = "Dashboard"

# Override admin index to add statistics
from django.utils import timezone
from datetime import timedelta

original_index = admin.site.index

def custom_admin_index(request, extra_context=None):
    from accounts.models import User, BroadcastNotification
    from activities.models import Activity
    from messaging.models import Message, Conversation
    from moderation.models import ReportedContent
    from fcm_django.models import FCMDevice
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(hours=24)
    
    # User stats
    total_users = User.objects.count()
    new_users_today = User.objects.filter(date_joined__gte=today_start).count()
    active_users_24h = User.objects.filter(last_active__gte=last_24h).count()
    active_percentage = round((active_users_24h / total_users * 100) if total_users > 0 else 0)
    
    # Mode distribution
    social_users = User.objects.filter(current_mode='social').count()
    professional_users = User.objects.filter(current_mode='professional').count()
    social_percentage = round((social_users / total_users * 100) if total_users > 0 else 0)
    professional_percentage = round((professional_users / total_users * 100) if total_users > 0 else 0)
    
    # Activity stats
    active_activities = Activity.objects.filter(status='active').count()
    activities_today = Activity.objects.filter(created_at__gte=today_start).count()
    
    # Message stats
    try:
        messages_today = Message.objects.filter(created_at__gte=today_start).count()
        conversations_count = Conversation.objects.count()
    except:
        messages_today = 0
        conversations_count = 0
    
    # Report stats
    try:
        pending_reports = ReportedContent.objects.filter(status='pending').count()
    except:
        pending_reports = 0
    
    # FCM stats
    try:
        fcm_devices = FCMDevice.objects.filter(active=True).count()
    except:
        fcm_devices = 0
    
    # Top category
    try:
        from activities.models import Category
        from django.db.models import Count
        top_category_data = Activity.objects.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count').first()
        top_category = top_category_data['category__name'] if top_category_data else "Kahve & Sohbet"
    except:
        top_category = "Kahve & Sohbet"
    
    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:5]
    
    extra_context = extra_context or {}
    extra_context.update({
        'stats': {
            'total_users': total_users,
            'new_users_today': new_users_today,
            'active_users_24h': active_users_24h,
            'active_percentage': active_percentage,
            'social_users': social_users,
            'professional_users': professional_users,
            'social_percentage': social_percentage,
            'professional_percentage': professional_percentage,
            'active_activities': active_activities,
            'activities_today': activities_today,
            'messages_today': messages_today,
            'conversations_count': conversations_count,
            'pending_reports': pending_reports,
            'fcm_devices': fcm_devices,
            'top_category': top_category,
        },
        'recent_users': recent_users,
    })
    
    return original_index(request, extra_context=extra_context)

admin.site.index = custom_admin_index

urlpatterns = [
    # Admin with custom dashboard
    path('admin/', admin.site.urls),
    
    # Legal Pages
    path('privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('terms/', TemplateView.as_view(template_name='legal/terms.html'), name='terms'),
    path('account-deletion/', TemplateView.as_view(template_name='legal/account_deletion.html'), name='account_deletion'),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # API Endpoints
    path('api/auth/', include('accounts.urls')),
    path('api/activities/', include('activities.urls')),
    path('api/messages/', include('messaging.urls')),
    path('api/reports/', include('moderation.urls')),
    
    # dj-rest-auth
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    
    # Social Auth - REST API endpoints
    path('api/auth/social/google/', accounts_views.GoogleLogin.as_view(), name='google_login'),
    path('api/auth/social/apple/', accounts_views.AppleLoginView.as_view(), name='apple_login'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

