"""
Activity models for GoDo.
Supports both Social and Professional modes with location features.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class ActivityCategory(models.Model):
    """Predefined activity categories."""
    
    MODE_CHOICES = [
        ('social', 'Sosyal'),
        ('professional', 'Profesyonel'),
        ('both', 'Her İkisi'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Kategori Adı')
    name_en = models.CharField(max_length=100, blank=True, verbose_name='İngilizce Adı')
    icon = models.CharField(max_length=50, blank=True, verbose_name='İkon')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='both', verbose_name='Mod')
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Aktivite Kategorisi'
        verbose_name_plural = 'Aktivite Kategorileri'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name


class Activity(models.Model):
    """
    Main activity model.
    Represents events/activities that users can join.
    """
    
    MODE_CHOICES = [
        ('social', 'Sosyal'),
        ('professional', 'Profesyonel'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Aktif'),
        ('full', 'Dolu'),
        ('completed', 'Tamamlandı'),
        ('cancelled', 'İptal Edildi'),
    ]
    
    # Creator
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_activities',
        verbose_name='Oluşturan'
    )
    
    # Basic Info
    title = models.CharField(max_length=200, verbose_name='Başlık')
    description = models.TextField(verbose_name='Açıklama')
    category = models.ForeignKey(
        ActivityCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activities',
        verbose_name='Kategori'
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='social', verbose_name='Mod')
    
    # Location (masked for privacy)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='Enlem')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, verbose_name='Boylam')
    address_display = models.CharField(max_length=200, verbose_name='Görünen Adres')  # e.g. "Kadıköy, ~500m"
    address_full = models.CharField(max_length=500, blank=True, verbose_name='Tam Adres')  # Only for approved participants
    city = models.CharField(max_length=100, blank=True, verbose_name='Şehir')
    district = models.CharField(max_length=100, blank=True, verbose_name='İlçe')
    
    # Timing
    start_time = models.DateTimeField(verbose_name='Başlangıç')
    end_time = models.DateTimeField(blank=True, null=True, verbose_name='Bitiş')
    
    # Participants
    max_participants = models.PositiveIntegerField(default=10, verbose_name='Maksimum Katılımcı')
    current_participants = models.PositiveIntegerField(default=0, verbose_name='Mevcut Katılımcı')
    
    # Social Mode: Instant Plans (1-3 hour activities)
    is_instant = models.BooleanField(default=False, verbose_name='Anlık Plan')
    
    # Social Mode: Group Joining
    is_group_join = models.BooleanField(default=False, verbose_name='Grup Olarak Katılım')
    group_size_min = models.PositiveIntegerField(default=1, verbose_name='Min Grup Boyutu')
    group_size_max = models.PositiveIntegerField(default=5, verbose_name='Max Grup Boyutu')
    
    # Professional Mode: Company/Campus Filter
    company_domain_filter = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Şirket Domain Filtresi'
    )
    
    # SEO: Public Web Pages (Optional)
    is_public_seo = models.BooleanField(default=False, verbose_name='Halka Açık (SEO)')
    seo_slug = models.SlugField(blank=True, null=True, unique=True, verbose_name='SEO URL')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='Durum')
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Oluşturulma')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Güncelleme')
    
    class Meta:
        verbose_name = 'Aktivite'
        verbose_name_plural = 'Aktiviteler'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['mode', 'status', 'is_active']),
            models.Index(fields=['city', 'district']),
            models.Index(fields=['start_time']),
            models.Index(fields=['is_public_seo', 'seo_slug']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.creator}"
    
    @property
    def is_full(self):
        return self.current_participants >= self.max_participants
    
    @property
    def spots_left(self):
        return max(0, self.max_participants - self.current_participants)
    
    @property
    def is_past(self):
        if self.end_time is None:
            return self.start_time < timezone.now()
        return self.end_time < timezone.now()
    
    def save(self, *args, **kwargs):
        # Auto-update status
        if self.is_full and self.status == 'active':
            self.status = 'full'
        elif self.is_past and self.status in ['active', 'full']:
            self.status = 'completed'
        
        super().save(*args, **kwargs)


class ActivityParticipation(models.Model):
    """
    Tracks user participation/application to activities.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Beklemede'),
        ('approved', 'Onaylandı'),
        ('rejected', 'Reddedildi'),
        ('cancelled', 'İptal Edildi'),
    ]
    
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='participations',
        verbose_name='Aktivite'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='participations',
        verbose_name='Katılımcı'
    )
    
    # Application
    message = models.TextField(blank=True, verbose_name='Başvuru Mesajı')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Durum')
    
    # Group Joining (Social Mode)
    is_group = models.BooleanField(default=False, verbose_name='Grup Olarak')
    group_member_count = models.PositiveIntegerField(default=1, verbose_name='Grup Üye Sayısı')
    group_members_info = models.JSONField(default=list, blank=True, verbose_name='Grup Üyeleri')
    
    # Timestamps
    applied_at = models.DateTimeField(auto_now_add=True, verbose_name='Başvuru Tarihi')
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name='Yanıt Tarihi')
    
    class Meta:
        verbose_name = 'Katılım'
        verbose_name_plural = 'Katılımlar'
        unique_together = ['activity', 'user']
        ordering = ['-applied_at']
    
    def __str__(self):
        return f"{self.user} → {self.activity.title}"
    
    def approve(self):
        """Approve participation and update activity count."""
        if self.status != 'approved':
            self.status = 'approved'
            self.responded_at = timezone.now()
            self.save()
            
            # Update activity participant count
            self.activity.current_participants += self.group_member_count
            self.activity.save(update_fields=['current_participants'])
    
    def reject(self):
        """Reject participation."""
        self.status = 'rejected'
        self.responded_at = timezone.now()
        self.save()


class ActivityImage(models.Model):
    """Images attached to activities."""
    
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='Aktivite'
    )
    image = models.ImageField(upload_to='activities/', verbose_name='Görsel')
    is_primary = models.BooleanField(default=False, verbose_name='Ana Görsel')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Aktivite Görseli'
        verbose_name_plural = 'Aktivite Görselleri'
        ordering = ['order']
    
    def __str__(self):
        return f"Image for {self.activity.title}"
