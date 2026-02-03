"""
Messaging models for GoDo.
Supports real-time chat with WebSocket integration.
"""

from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """
    Chat conversation between users.
    Can be linked to an activity or be direct messaging.
    """
    
    TYPE_CHOICES = [
        ('activity', 'Aktivite Sohbeti'),
        ('direct', 'Direkt Mesaj'),
    ]
    
    activity = models.ForeignKey(
        'activities.Activity',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversations',
        verbose_name='Aktivite'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conversations',
        verbose_name='Katılımcılar'
    )
    conversation_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='direct',
        verbose_name='Tip'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma')
    last_message_at = models.DateTimeField(auto_now=True, verbose_name='Son Mesaj')
    
    class Meta:
        verbose_name = 'Sohbet'
        verbose_name_plural = 'Sohbetler'
        ordering = ['-last_message_at']
    
    def __str__(self):
        if self.activity:
            return f"Sohbet: {self.activity.title}"
        participants = self.participants.all()[:3]
        names = [p.display_name or p.email.split('@')[0] for p in participants]
        return f"Sohbet: {', '.join(names)}"
    
    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()
    
    @property
    def unread_count_for(self):
        """Returns a method to get unread count for a specific user."""
        def get_count(user):
            return self.messages.filter(is_read=False).exclude(sender=user).count()
        return get_count


class Message(models.Model):
    """
    Individual message in a conversation.
    Content is filtered for UGC compliance.
    """
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Sohbet'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Gönderen'
    )
    
    # Content
    content = models.TextField(verbose_name='İçerik')
    is_filtered = models.BooleanField(default=False, verbose_name='Filtrelendi')
    original_content = models.TextField(blank=True, verbose_name='Orijinal İçerik')
    
    # Status
    is_read = models.BooleanField(default=False, verbose_name='Okundu')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Okunma Zamanı')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Gönderilme')
    
    class Meta:
        verbose_name = 'Mesaj'
        verbose_name_plural = 'Mesajlar'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.sender}: {self.content[:50]}..."
    
    def mark_as_read(self):
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class TypingIndicator(models.Model):
    """
    Tracks typing status for real-time indicators.
    Ephemeral - cleaned up periodically.
    """
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='typing_indicators'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    started_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['conversation', 'user']
    
    @classmethod
    def cleanup_old(cls):
        """Remove typing indicators older than 10 seconds."""
        from django.utils import timezone
        from datetime import timedelta
        
        threshold = timezone.now() - timedelta(seconds=10)
        cls.objects.filter(started_at__lt=threshold).delete()
