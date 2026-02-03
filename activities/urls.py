"""
URL patterns for activities app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.ActivityViewSet, basename='activity')

app_name = 'activities'

urlpatterns = [
    # Categories
    path('categories/', views.ActivityCategoryListView.as_view(), name='categories'),
    
    # Public SEO page
    path('public/<slug:seo_slug>/', views.PublicActivityDetailView.as_view(), name='public-activity'),
    
    # ViewSet routes
    path('', include(router.urls)),
]
