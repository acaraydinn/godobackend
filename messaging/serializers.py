"""
Serializers for messaging app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, Message
from accounts.serializers import UserPublicSerializer

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages."""
    
    sender = UserPublicSerializer(read_only=True)
    is_mine = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'content', 'is_filtered', 'is_read', 'read_at', 'created_at', 'is_mine']
        read_only_fields = ['id', 'sender', 'is_filtered', 'is_read', 'read_at', 'created_at']
    
    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.sender == request.user
        return False


class ConversationListSerializer(serializers.ModelSerializer):
    """Serializer for conversation list."""
    
    participants = UserPublicSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    activity_title = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'conversation_type', 'participants', 'activity_title',
            'last_message', 'unread_count', 'last_message_at', 'created_at'
        ]
    
    def get_last_message(self, obj):
        message = obj.last_message
        if message:
            return {
                'content': message.content[:100],
                'sender_name': message.sender.display_name or message.sender.email.split('@')[0],
                'created_at': message.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0
    
    def get_activity_title(self, obj):
        if obj.activity:
            return obj.activity.title
        return None


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Serializer for conversation with messages."""
    
    participants = UserPublicSerializer(many=True, read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    activity_title = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'conversation_type', 'participants', 'activity_title',
            'messages', 'last_message_at', 'created_at'
        ]
    
    def get_activity_title(self, obj):
        if obj.activity:
            return obj.activity.title
        return None


class CreateConversationSerializer(serializers.Serializer):
    """Serializer for creating a new conversation."""
    
    participant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=10
    )
    activity_id = serializers.IntegerField(required=False, allow_null=True)
    initial_message = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending a message."""
    
    content = serializers.CharField(max_length=2000)
