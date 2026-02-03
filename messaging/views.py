"""
Views for messaging app.
"""

from django.db.models import Q
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import BlockedUser
from moderation.utils import filter_ugc_content
from .models import Conversation, Message
from .serializers import (
    ConversationListSerializer, ConversationDetailSerializer,
    CreateConversationSerializer, SendMessageSerializer, MessageSerializer
)


class ConversationListView(generics.ListAPIView):
    """List all conversations for current user."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationListSerializer
    
    def get_queryset(self):
        return Conversation.objects.filter(
            participants=self.request.user
        ).prefetch_related('participants', 'messages')


class ConversationDetailView(generics.RetrieveAPIView):
    """Get conversation with messages."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationDetailSerializer
    
    def get_queryset(self):
        return Conversation.objects.filter(participants=self.request.user)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Mark messages as read
        instance.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CreateConversationView(APIView):
    """Create a new conversation."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        participant_ids = serializer.validated_data['participant_ids']
        activity_id = serializer.validated_data.get('activity_id')
        initial_message = serializer.validated_data.get('initial_message', '')
        
        # Check for blocked users
        blocked_ids = set(BlockedUser.objects.filter(
            Q(blocker=request.user) | Q(blocked=request.user)
        ).values_list('blocker_id', 'blocked_id').distinct())
        
        blocked_flat = set()
        for b in blocked_ids:
            blocked_flat.update(b)
        
        if any(pid in blocked_flat for pid in participant_ids):
            return Response(
                {'error': 'Engellenmiş kullanıcılarla sohbet başlatamazsınız.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if conversation already exists (for direct messages)
        if not activity_id and len(participant_ids) == 1:
            existing = Conversation.objects.filter(
                participants=request.user,
                conversation_type='direct'
            ).filter(
                participants=participant_ids[0]
            ).first()
            
            if existing and existing.participants.count() == 2:
                return Response(
                    ConversationDetailSerializer(existing, context={'request': request}).data
                )
        
        # Create conversation
        conversation = Conversation.objects.create(
            activity_id=activity_id,
            conversation_type='activity' if activity_id else 'direct'
        )
        
        # Add participants
        conversation.participants.add(request.user)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        participants = User.objects.filter(id__in=participant_ids, is_active=True)
        conversation.participants.add(*participants)
        
        # Send initial message if provided
        if initial_message:
            result = filter_ugc_content(initial_message)
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=result['filtered_text'] if not result['is_clean'] else initial_message,
                is_filtered=not result['is_clean'],
                original_content=initial_message if not result['is_clean'] else ''
            )
        
        return Response(
            ConversationDetailSerializer(conversation, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class SendMessageView(APIView):
    """Send a message in a conversation."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                participants=request.user
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Sohbet bulunamadı.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        content = serializer.validated_data['content']
        
        # Filter content
        result = filter_ugc_content(content)
        
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=result['filtered_text'] if not result['is_clean'] else content,
            is_filtered=not result['is_clean'],
            original_content=content if not result['is_clean'] else ''
        )
        
        # Update conversation timestamp
        conversation.save()  # Triggers auto_now on last_message_at
        
        # TODO: Send WebSocket notification to other participants
        # TODO: Send push notification to offline users
        
        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class MarkMessagesReadView(APIView):
    """Mark all messages in a conversation as read."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                participants=request.user
            )
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Sohbet bulunamadı.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        updated = conversation.messages.filter(
            is_read=False
        ).exclude(
            sender=request.user
        ).update(is_read=True)
        
        return Response({'marked_read': updated})
