"""
URL patterns for moderation app.
"""

from django.urls import path
from . import views

app_name = 'moderation'

urlpatterns = [
    path('', views.CreateReportView.as_view(), name='create-report'),
]
