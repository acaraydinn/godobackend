"""
Moderation models for GoDo.
Handles content reporting and moderation for App Store compliance.
"""

from django.db import models
from django.conf import settings


class ReportedContent(models.Model):
    """
    User-generated reports for inappropriate content.
    Required for App Store/Play Store compliance.
    """
    
    REPORT_TYPE_CHOICES = [
        ('activity', 'Aktivite'),
        ('user', 'Kullanıcı'),
        ('message', 'Mesaj'),
    ]
    
    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Uygunsuz İçerik'),
        ('harassment', 'Taciz'),
        ('hate_speech', 'Nefret Söylemi'),
        ('violence', 'Şiddet'),
        ('scam', 'Dolandırıcılık'),
        ('fake_profile', 'Sahte Profil'),
        ('other', 'Diğer'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Beklemede'),
        ('reviewed', 'İncelendi'),
        ('action_taken', 'İşlem Yapıldı'),
        ('dismissed', 'Reddedildi'),
    ]
    
    # Reporter
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='filed_reports',
        verbose_name='Şikayet Eden'
    )
    
    # Content type
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        verbose_name='Şikayet Tipi'
    )
    
    # Reported entities (only one should be set)
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports_against',
        verbose_name='Şikayet Edilen Kullanıcı'
    )
    reported_activity = models.ForeignKey(
        'activities.Activity',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
        verbose_name='Şikayet Edilen Aktivite'
    )
    reported_message = models.ForeignKey(
        'messaging.Message',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports',
        verbose_name='Şikayet Edilen Mesaj'
    )
    
    # Report details
    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        verbose_name='Sebep'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Açıklama'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Durum'
    )
    
    # Admin notes
    admin_notes = models.TextField(blank=True, verbose_name='Yönetici Notları')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports',
        verbose_name='İnceleyen'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='İnceleme Tarihi')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncelleme')
    
    class Meta:
        verbose_name = 'Şikayet'
        verbose_name_plural = 'Şikayetler'
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.reported_user or self.reported_activity or self.reported_message
        return f"Şikayet: {self.get_reason_display()} - {target}"


class BannedWord(models.Model):
    """
    Words/phrases banned from UGC content.
    Used by the content filter.
    """
    
    word = models.CharField(max_length=100, unique=True, verbose_name='Kelime')
    is_regex = models.BooleanField(default=False, verbose_name='Regex')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Yasaklı Kelime'
        verbose_name_plural = 'Yasaklı Kelimeler'
    
    def __str__(self):
        return self.word


class ModerationLog(models.Model):
    """
    Audit log for moderation actions.
    """
    
    ACTION_CHOICES = [
        ('warn', 'Uyarı'),
        ('content_removed', 'İçerik Silindi'),
        ('user_suspended', 'Kullanıcı Askıya Alındı'),
        ('user_banned', 'Kullanıcı Yasaklandı'),
        ('report_dismissed', 'Şikayet Reddedildi'),
    ]
    
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='moderation_actions',
        verbose_name='Moderatör'
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='moderation_received',
        verbose_name='Hedef Kullanıcı'
    )
    report = models.ForeignKey(
        ReportedContent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='İlgili Şikayet'
    )
    
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name='İşlem')
    reason = models.TextField(verbose_name='Gerekçe')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Tarih')
    
    class Meta:
        verbose_name = 'Moderasyon Logu'
        verbose_name_plural = 'Moderasyon Logları'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.target_user}"
