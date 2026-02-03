"""
Serializers for accounts app.
Handles user registration, profile, and authentication.
"""

from rest_framework import serializers
from dj_rest_auth.registration.serializers import RegisterSerializer
from django.contrib.auth import get_user_model
from .models import BlockedUser, LegalDocument, UserPhoto

User = get_user_model()


class CustomRegisterSerializer(RegisterSerializer):
    """Extended registration with display_name and legal consent."""
    
    username = None  # Remove username field
    display_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    terms_accepted = serializers.BooleanField(required=True)
    
    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError('Kullanım şartlarını kabul etmelisiniz.')
        return value
    
    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data['display_name'] = self.validated_data.get('display_name', '')
        data['phone'] = self.validated_data.get('phone', '')
        return data
    
    def save(self, request):
        user = super().save(request)
        user.display_name = self.cleaned_data.get('display_name', '')
        user.phone = self.cleaned_data.get('phone') or None
        if self.validated_data.get('terms_accepted'):
            from django.utils import timezone
            user.terms_accepted_at = timezone.now()
            user.data_consent_at = timezone.now()
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    """Full user profile serializer."""
    
    is_professional_verified = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone', 'display_name', 'avatar', 'bio',
            'current_mode', 'github_url', 'linkedin_url', 'portfolio_url', 'skills',
            'twitter_url', 'instagram_url', 'socialrate_url',
            'is_verified_company', 'company_name',
            'is_2fa_enabled', 'is_professional_verified',
            'date_joined', 'last_active'
        ]
        read_only_fields = ['id', 'email', 'is_verified_company', 'date_joined', 'last_active']


class UserPublicSerializer(serializers.ModelSerializer):
    """Public user profile (limited info for other users)."""
    
    class Meta:
        model = User
        fields = [
            'id', 'display_name', 'avatar', 'bio',
            'current_mode', 'github_url', 'linkedin_url', 'portfolio_url',
            'twitter_url', 'instagram_url', 'socialrate_url',
            'is_verified_company', 'company_name'
        ]


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""
    
    class Meta:
        model = User
        fields = [
            'display_name', 'avatar', 'bio', 'current_mode',
            'github_url', 'linkedin_url', 'portfolio_url', 'skills',
            'twitter_url', 'instagram_url', 'socialrate_url'
        ]


class PrivacySettingsSerializer(serializers.ModelSerializer):
    """Serializer for privacy dashboard."""
    
    class Meta:
        model = User
        fields = ['privacy_settings', 'data_consent_at', 'terms_accepted_at']
        read_only_fields = ['data_consent_at', 'terms_accepted_at']


class BlockedUserSerializer(serializers.ModelSerializer):
    """Serializer for blocked users list."""
    
    blocked_user = UserPublicSerializer(source='blocked', read_only=True)
    
    class Meta:
        model = BlockedUser
        fields = ['id', 'blocked_user', 'created_at', 'reason']
        read_only_fields = ['id', 'created_at']


class BlockUserSerializer(serializers.Serializer):
    """Serializer for blocking a user."""
    
    user_id = serializers.IntegerField()
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class FCMTokenSerializer(serializers.Serializer):
    """Serializer for updating FCM token."""
    
    fcm_token = serializers.CharField()
    device_type = serializers.ChoiceField(choices=['android', 'ios', 'web'], default='android')


class LegalDocumentSerializer(serializers.ModelSerializer):
    """Serializer for legal documents."""
    
    class Meta:
        model = LegalDocument
        fields = ['slug', 'title', 'document_type', 'content', 'version', 'updated_at']


class VerifyCompanyEmailSerializer(serializers.Serializer):
    """Serializer for company email verification."""
    
    company_email = serializers.EmailField()
    
    def validate_company_email(self, value):
        # Check if domain is allowed (not common public domains)
        public_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com']
        domain = value.split('@')[1].lower()
        
        if domain in public_domains:
            raise serializers.ValidationError('Kurumsal e-posta adresi kullanmalısınız.')
        
        return value


class TwoFactorSetupSerializer(serializers.Serializer):
    """Serializer for 2FA setup."""
    
    pass  # Will return QR code and secret


class TwoFactorVerifySerializer(serializers.Serializer):
    """Serializer for 2FA verification."""
    
    code = serializers.CharField(max_length=6, min_length=6)


class AccountDeleteSerializer(serializers.Serializer):
    """
    Serializer for account deletion.
    GDPR/KVKK compliant - requires password confirmation.
    """
    
    password = serializers.CharField(write_only=True)
    confirm_deletion = serializers.BooleanField()
    
    def validate_confirm_deletion(self, value):
        if not value:
            raise serializers.ValidationError('Hesap silme işlemini onaylamalısınız.')
        return value
    
    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Yanlış şifre.')
        return value


class UserPhotoSerializer(serializers.ModelSerializer):
    """Serializer for user profile photos."""
    
    class Meta:
        model = UserPhoto
        fields = ['id', 'image', 'is_primary', 'order', 'created_at']
        read_only_fields = ['id', 'order', 'created_at']


class PhotoReorderSerializer(serializers.Serializer):
    """Serializer for reordering photos."""
    
    photo_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of photo IDs in desired order"
    )
