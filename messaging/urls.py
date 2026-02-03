"""
URL patterns for messaging app.
"""

from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    # Conversations
    path('conversations/', views.ConversationListView.as_view(), name='conversation-list'),
    path('conversations/create/', views.CreateConversationView.as_view(), name='conversation-create'),
    path('conversations/<int:pk>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    
    # Messages
    path('conversations/<int:conversation_id>/send/', views.SendMessageView.as_view(), name='send-message'),
    path('conversations/<int:conversation_id>/read/', views.MarkMessagesReadView.as_view(), name='mark-read'),
]
