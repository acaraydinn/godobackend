"""
WebSocket consumers for real-time messaging.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat.
    Handles message sending and typing indicators.
    """
    
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        # Verify user is participant
        is_participant = await self.check_participant()
        if not is_participant:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'read':
                await self.handle_read(data)
        except json.JSONDecodeError:
            pass
    
    async def handle_chat_message(self, data):
        """Handle incoming chat message."""
        content = data.get('content', '').strip()
        if not content:
            return
        
        # Save message to database
        message_data = await self.save_message(content)
        
        # Broadcast to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )
    
    async def handle_typing(self, data):
        """Handle typing indicator."""
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'user_name': self.user.display_name or self.user.email.split('@')[0],
                'is_typing': is_typing
            }
        )
    
    async def handle_read(self, data):
        """Handle read receipt."""
        await self.mark_messages_read()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'messages_read',
                'user_id': self.user.id
            }
        )
    
    async def chat_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    async def messages_read(self, event):
        """Send read receipt to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'read',
            'user_id': event['user_id']
        }))
    
    @database_sync_to_async
    def check_participant(self):
        """Check if user is participant in conversation."""
        from .models import Conversation
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user
        ).exists()
    
    @database_sync_to_async
    def save_message(self, content):
        """Save message to database and return serialized data."""
        from .models import Conversation, Message
        from moderation.utils import filter_ugc_content
        
        conversation = Conversation.objects.get(id=self.conversation_id)
        
        # Filter content
        result = filter_ugc_content(content)
        
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=result['filtered_text'] if not result['is_clean'] else content,
            is_filtered=not result['is_clean'],
            original_content=content if not result['is_clean'] else ''
        )
        
        # Update conversation timestamp
        conversation.save()
        
        return {
            'id': message.id,
            'sender': {
                'id': self.user.id,
                'display_name': self.user.display_name or self.user.email.split('@')[0],
                'avatar': self.user.avatar.url if self.user.avatar else None
            },
            'content': message.content,
            'is_filtered': message.is_filtered,
            'created_at': message.created_at.isoformat()
        }
    
    @database_sync_to_async
    def mark_messages_read(self):
        """Mark all messages as read."""
        from .models import Conversation
        
        conversation = Conversation.objects.get(id=self.conversation_id)
        conversation.messages.filter(
            is_read=False
        ).exclude(
            sender=self.user
        ).update(is_read=True)
