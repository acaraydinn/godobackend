"""
User model and related models for GoDo application.
Includes safety models (BlockedUser, ReportedContent) for App Store compliance.
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email adresi zorunludur')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with email as primary identifier.
    Supports both Social and Professional modes.
    """
    
    MODE_CHOICES = [
        ('social', 'Sosyal'),
        ('professional', 'Profesyonel'),
    ]
    
    # Core Fields
    email = models.EmailField(unique=True, verbose_name='E-posta')
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True, verbose_name='Telefon')
    display_name = models.CharField(max_length=100, blank=True, verbose_name='Görünen Ad')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name='Profil Fotoğrafı')
    bio = models.TextField(max_length=500, blank=True, verbose_name='Hakkımda')
    
    # Mode Settings
    current_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='social', verbose_name='Aktif Mod')
    
    # Professional Mode Fields
    github_url = models.URLField(blank=True, null=True, verbose_name='GitHub Profili')
    linkedin_url = models.URLField(blank=True, null=True, verbose_name='LinkedIn Profili')
    portfolio_url = models.URLField(blank=True, null=True, verbose_name='Portfolyo')
    skills = models.JSONField(default=list, blank=True, verbose_name='Yetenekler')
    
    # Social Media Links
    twitter_url = models.URLField(blank=True, null=True, verbose_name='X (Twitter) Profili')
    instagram_url = models.URLField(blank=True, null=True, verbose_name='Instagram Profili')
    socialrate_url = models.URLField(blank=True, null=True, verbose_name='SocialRate Profili')
    
    # Company/Campus Verification
    is_verified_company = models.BooleanField(default=False, verbose_name='Şirket Doğrulandı')
    company_domain = models.CharField(max_length=100, blank=True, null=True, verbose_name='Şirket Domaini')
    company_name = models.CharField(max_length=200, blank=True, null=True, verbose_name='Şirket/Üniversite Adı')
    
    # Push Notifications
    fcm_token = models.TextField(blank=True, null=True, verbose_name='FCM Token')
    
    # Two-Factor Authentication
    is_2fa_enabled = models.BooleanField(default=False, verbose_name='2FA Aktif')
    two_factor_secret = models.CharField(max_length=100, blank=True, null=True)
    
    # Privacy Settings (GDPR/KVKK)
    privacy_settings = models.JSONField(default=dict, blank=True, verbose_name='Gizlilik Ayarları')
    data_consent_at = models.DateTimeField(blank=True, null=True, verbose_name='Veri Onay Tarihi')
    terms_accepted_at = models.DateTimeField(blank=True, null=True, verbose_name='Şartlar Onay Tarihi')
    
    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now, verbose_name='Kayıt Tarihi')
    last_active = models.DateTimeField(auto_now=True, verbose_name='Son Aktiflik')
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = 'Kullanıcı'
        verbose_name_plural = 'Kullanıcılar'
    
    def __str__(self):
        return self.display_name or self.email.split('@')[0]
    
    def get_full_name(self):
        return self.display_name or self.email.split('@')[0]
    
    def get_short_name(self):
        return self.display_name or self.email.split('@')[0]
    
    @property
    def is_professional_verified(self):
        """Check if user has verified professional credentials."""
        return bool(self.github_url or self.linkedin_url or self.portfolio_url)


class BlockedUser(models.Model):
    """
    User blocking relationship for safety.
    Required for App Store compliance.
    """
    
    blocker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blocking',
        verbose_name='Engelleyen'
    )
    blocked = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='blocked_by',
        verbose_name='Engellenen'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Engellenme Tarihi')
    reason = models.TextField(blank=True, verbose_name='Sebep')
    
    class Meta:
        verbose_name = 'Engellenen Kullanıcı'
        verbose_name_plural = 'Engellenen Kullanıcılar'
        unique_together = ['blocker', 'blocked']
    
    def __str__(self):
        return f"{self.blocker} → {self.blocked}"


class OTP(models.Model):
    """One-Time Password for phone/email verification."""
    
    TYPE_CHOICES = [
        ('email', 'E-posta'),
        ('phone', 'Telefon'),
        ('2fa', 'İki Faktörlü Doğrulama'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    otp_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='email')
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Doğrulama Kodu'
        verbose_name_plural = 'Doğrulama Kodları'
    
    def __str__(self):
        return f"{self.user} - {self.otp_type}"
    
    @property
    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


class LegalDocument(models.Model):
    """
    Legal documents for GDPR/KVKK compliance.
    Served via API for both web and mobile.
    """
    
    DOCUMENT_TYPES = [
        ('privacy_policy', 'Gizlilik Politikası'),
        ('terms_of_service', 'Kullanım Şartları'),
        ('kvkk', 'KVKK Aydınlatma Metni'),
        ('cookie_policy', 'Çerez Politikası'),
    ]
    
    slug = models.SlugField(unique=True, verbose_name='URL Slug')
    title = models.CharField(max_length=200, verbose_name='Başlık')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, verbose_name='Belge Tipi')
    content = models.TextField(verbose_name='İçerik (HTML)')
    version = models.CharField(max_length=20, default='1.0', verbose_name='Versiyon')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Yasal Belge'
        verbose_name_plural = 'Yasal Belgeler'
    
    def __str__(self):
        return f"{self.title} (v{self.version})"


class UserPhoto(models.Model):
    """
    User profile photos.
    Allows users to upload multiple photos for their profile.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name='Kullanıcı'
    )
    image = models.ImageField(
        upload_to='user_photos/',
        verbose_name='Fotoğraf'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Ana Fotoğraf'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='Sıra'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Yüklenme Tarihi'
    )
    
    class Meta:
        verbose_name = 'Kullanıcı Fotoğrafı'
        verbose_name_plural = 'Kullanıcı Fotoğrafları'
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return f"{self.user} - Fotoğraf {self.order + 1}"
    
    def save(self, *args, **kwargs):
        # If this is set as primary, unset other primary photos
        if self.is_primary:
            UserPhoto.objects.filter(user=self.user, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class BroadcastNotification(models.Model):
    """
    Model for storing sent broadcast notifications.
    Used for tracking and analytics.
    """
    
    title = models.CharField(max_length=200, verbose_name='Başlık')
    body = models.TextField(verbose_name='İçerik')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='Gönderim Tarihi')
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Gönderen'
    )
    devices_reached = models.IntegerField(default=0, verbose_name='Ulaşılan Cihaz')
    
    class Meta:
        verbose_name = 'Toplu Bildirim'
        verbose_name_plural = 'Toplu Bildirimler'
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.title} ({self.sent_at.strftime('%d.%m.%Y %H:%M') if self.sent_at else 'Bekliyor'})"
