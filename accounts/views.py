"""
Views for accounts app.
Handles user profile, blocking, 2FA, and account management.
"""

import random
import string
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from fcm_django.models import FCMDevice

from .models import BlockedUser, OTP, LegalDocument
from .serializers import (
    UserSerializer, UserUpdateSerializer, UserPublicSerializer,
    PrivacySettingsSerializer, BlockedUserSerializer, BlockUserSerializer,
    FCMTokenSerializer, LegalDocumentSerializer, VerifyCompanyEmailSerializer,
    TwoFactorSetupSerializer, TwoFactorVerifySerializer, AccountDeleteSerializer
)

User = get_user_model()


class CurrentUserView(generics.RetrieveUpdateAPIView):
    """Get or update current user profile."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_object(self):
        return self.request.user


class UserPublicProfileView(generics.RetrieveAPIView):
    """View another user's public profile."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPublicSerializer
    queryset = User.objects.filter(is_active=True)
    
    def get_queryset(self):
        # Exclude blocked users
        blocked_ids = BlockedUser.objects.filter(
            blocker=self.request.user
        ).values_list('blocked_id', flat=True)
        
        return User.objects.filter(is_active=True).exclude(id__in=blocked_ids)


class PrivacySettingsView(generics.RetrieveUpdateAPIView):
    """
    View and update privacy settings.
    GDPR/KVKK compliant privacy dashboard.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PrivacySettingsSerializer
    
    def get_object(self):
        return self.request.user


class BlockedUsersListView(generics.ListAPIView):
    """List all blocked users."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BlockedUserSerializer
    
    def get_queryset(self):
        return BlockedUser.objects.filter(blocker=self.request.user)


class BlockUserView(APIView):
    """Block or unblock a user."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, user_id):
        """Block a user."""
        if request.user.id == user_id:
            return Response(
                {'error': 'Kendinizi engelleyemezsiniz.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_to_block = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {'error': 'Kullanıcı bulunamadı.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        blocked, created = BlockedUser.objects.get_or_create(
            blocker=request.user,
            blocked=user_to_block,
            defaults={'reason': request.data.get('reason', '')}
        )
        
        if not created:
            return Response(
                {'message': 'Bu kullanıcı zaten engellenmiş.'},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'message': 'Kullanıcı başarıyla engellendi.'},
            status=status.HTTP_201_CREATED
        )
    
    def delete(self, request, user_id):
        """Unblock a user."""
        deleted, _ = BlockedUser.objects.filter(
            blocker=request.user,
            blocked_id=user_id
        ).delete()
        
        if deleted:
            return Response(
                {'message': 'Kullanıcının engeli kaldırıldı.'},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'error': 'Bu kullanıcı engellenmiş değil.'},
            status=status.HTTP_404_NOT_FOUND
        )


class UpdateFCMTokenView(APIView):
    """Update user's FCM token for push notifications."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = FCMTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        fcm_token = serializer.validated_data['fcm_token']
        device_type = serializer.validated_data['device_type']
        
        # Update user's FCM token
        request.user.fcm_token = fcm_token
        request.user.save(update_fields=['fcm_token'])
        
        # Update or create FCM device
        FCMDevice.objects.update_or_create(
            registration_id=fcm_token,
            defaults={
                'user': request.user,
                'type': device_type,
                'active': True
            }
        )
        
        return Response({'message': 'FCM token güncellendi.'})


class SendTestNotificationView(APIView):
    """Send a test push notification to the current user."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Send a test notification to the user's device."""
        try:
            from firebase_admin.messaging import Message, Notification
            
            # Get user's FCM devices
            devices = FCMDevice.objects.filter(user=request.user, active=True)
            
            if not devices.exists():
                return Response(
                    {'error': 'Kayıtlı cihaz bulunamadı. Bildirimlerin açık olduğundan emin olun.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            title = request.data.get('title', '🎉 Test Bildirimi')
            body = request.data.get('body', 'GoDo bildirimleri çalışıyor!')
            
            # Create message using Firebase Admin SDK format
            message = Message(
                notification=Notification(
                    title=title,
                    body=body,
                ),
                data={
                    'type': 'test',
                    'user_id': str(request.user.id)
                }
            )
            
            # Send notification to all devices
            result = devices.send_message(message)
            
            # Log the result for debugging
            print(f"FCM Send Result: {result}")
            
            return Response({
                'message': 'Test bildirimi gönderildi!',
                'devices_count': devices.count(),
                'result': str(result) if result else None,
            })
            
        except Exception as e:
            import traceback
            print(f"FCM Error: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': f'Bildirim gönderilemedi: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VerifyCompanyEmailView(APIView):
    """
    Verify company/campus email for Professional mode.
    Sends OTP to verify email ownership.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = VerifyCompanyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        company_email = serializer.validated_data['company_email']
        domain = company_email.split('@')[1]
        
        # Generate OTP
        code = ''.join(random.choices(string.digits, k=6))
        
        OTP.objects.create(
            user=request.user,
            code=code,
            otp_type='email',
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        # TODO: Send email with OTP code
        # send_verification_email(company_email, code)
        
        return Response({
            'message': f'Doğrulama kodu {company_email} adresine gönderildi.',
            'domain': domain
        })
    
    def put(self, request):
        """Verify OTP and update company status."""
        code = request.data.get('code')
        company_email = request.data.get('company_email')
        
        if not code or not company_email:
            return Response(
                {'error': 'Kod ve e-posta gerekli.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp = OTP.objects.filter(
            user=request.user,
            code=code,
            otp_type='email',
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if not otp:
            return Response(
                {'error': 'Geçersiz veya süresi dolmuş kod.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark OTP as used
        otp.is_used = True
        otp.save()
        
        # Update user's company verification
        domain = company_email.split('@')[1]
        request.user.is_verified_company = True
        request.user.company_domain = domain
        request.user.save(update_fields=['is_verified_company', 'company_domain'])
        
        return Response({
            'message': 'Şirket e-postası doğrulandı.',
            'domain': domain
        })


class TwoFactorSetupView(APIView):
    """Enable 2FA for web login."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        import pyotp
        
        # Generate secret
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        
        # Store secret temporarily
        request.user.two_factor_secret = secret
        request.user.save(update_fields=['two_factor_secret'])
        
        # Generate provisioning URI for QR code
        provisioning_uri = totp.provisioning_uri(
            name=request.user.email,
            issuer_name='GoDo'
        )
        
        return Response({
            'secret': secret,
            'qr_uri': provisioning_uri
        })


class TwoFactorVerifyView(APIView):
    """Verify 2FA code and enable/verify 2FA."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        import pyotp
        
        code = serializer.validated_data['code']
        secret = request.user.two_factor_secret
        
        if not secret:
            return Response(
                {'error': '2FA henüz kurulmamış.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        totp = pyotp.TOTP(secret)
        
        if totp.verify(code):
            request.user.is_2fa_enabled = True
            request.user.save(update_fields=['is_2fa_enabled'])
            
            return Response({'message': '2FA başarıyla etkinleştirildi.'})
        
        return Response(
            {'error': 'Geçersiz kod.'},
            status=status.HTTP_400_BAD_REQUEST
        )


class AccountDeleteView(APIView):
    """
    Delete user account permanently.
    GDPR/KVKK compliant - removes all user data.
    """
    
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request):
        serializer = AccountDeleteSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Delete all related data
        # - Activities created by user
        # - Participations
        # - Messages
        # - Blocked users
        # - FCM devices
        # - OTPs
        
        FCMDevice.objects.filter(user=user).delete()
        BlockedUser.objects.filter(Q(blocker=user) | Q(blocked=user)).delete()
        OTP.objects.filter(user=user).delete()
        
        # Anonymize and deactivate (keeps data integrity for other users' references)
        user.email = f'deleted_{user.id}@deleted.godo'
        user.phone = None
        user.display_name = 'Silinmiş Kullanıcı'
        user.avatar = None
        user.bio = ''
        user.fcm_token = None
        user.is_active = False
        user.privacy_settings = {}
        user.save()
        
        return Response({'message': 'Hesabınız başarıyla silindi.'})


class LegalDocumentView(generics.RetrieveAPIView):
    """Retrieve legal document by slug."""
    
    permission_classes = [permissions.AllowAny]
    serializer_class = LegalDocumentSerializer
    queryset = LegalDocument.objects.filter(is_active=True)
    lookup_field = 'slug'


class LegalDocumentListView(generics.ListAPIView):
    """List all legal documents."""
    
    permission_classes = [permissions.AllowAny]
    serializer_class = LegalDocumentSerializer
    queryset = LegalDocument.objects.filter(is_active=True)


# Social Authentication Views
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
import jwt
import requests
from jwt.algorithms import RSAAlgorithm
from rest_framework_simplejwt.tokens import RefreshToken


class GoogleLogin(SocialLoginView):
    """
    Google Social Login endpoint.
    Accepts access_token from Google Sign-In.
    """
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:3000"  # Not used for mobile
    client_class = OAuth2Client


class AppleLoginView(APIView):
    """
    Custom Apple Sign In endpoint.
    Validates id_token directly from Apple without needing server-side credentials.
    """
    permission_classes = [permissions.AllowAny]
    
    # Apple's public keys endpoint
    APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
    APPLE_ISSUER = "https://appleid.apple.com"
    APPLE_AUDIENCE = "com.godoapp.mobile"  # Your Bundle ID
    
    def post(self, request):
        id_token = request.data.get('id_token')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not id_token:
            return Response(
                {'error': 'id_token gerekli'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get Apple's public keys
            apple_keys = requests.get(self.APPLE_KEYS_URL).json()['keys']
            
            # Decode token header to get key id
            token_headers = jwt.get_unverified_header(id_token)
            kid = token_headers['kid']
            
            # Find the matching key
            apple_key = None
            for key in apple_keys:
                if key['kid'] == kid:
                    apple_key = key
                    break
            
            if not apple_key:
                return Response(
                    {'error': 'Apple public key bulunamadı'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Convert JWK to PEM public key
            public_key = RSAAlgorithm.from_jwk(apple_key)
            
            # Verify and decode the token
            decoded = jwt.decode(
                id_token,
                public_key,
                algorithms=['RS256'],
                audience=self.APPLE_AUDIENCE,
                issuer=self.APPLE_ISSUER,
            )
            
            # Extract user info
            apple_user_id = decoded['sub']
            email = decoded.get('email', f'{apple_user_id}@privaterelay.appleid.com')
            email_verified = decoded.get('email_verified', False)
            
            # Find or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'display_name': f'{first_name} {last_name}'.strip() or email.split('@')[0],
                    'is_active': True,
                }
            )
            
            # Update name if provided and user exists
            if not created and first_name:
                user.display_name = f'{first_name} {last_name}'.strip()
                user.save(update_fields=['display_name'])
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'display_name': user.display_name,
                }
            })
            
        except jwt.ExpiredSignatureError:
            return Response(
                {'error': 'Token süresi dolmuş'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except jwt.InvalidTokenError as e:
            return Response(
                {'error': f'Geçersiz token: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Apple Sign In hatası: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )


# User Photo Management Views
from .models import UserPhoto
from .serializers import UserPhotoSerializer, PhotoReorderSerializer
from rest_framework.parsers import MultiPartParser, FormParser


class UserPhotoListCreateView(generics.ListCreateAPIView):
    """List and upload user photos (max 10)."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPhotoSerializer
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        return UserPhoto.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Check max limit
        if UserPhoto.objects.filter(user=self.request.user).count() >= 10:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Maksimum 10 fotoğraf yükleyebilirsiniz.')
        
        # Set order to last
        last_order = UserPhoto.objects.filter(user=self.request.user).count()
        
        # If this is first photo, make it primary
        is_first = last_order == 0
        serializer.save(
            user=self.request.user,
            order=last_order,
            is_primary=is_first
        )


class UserPhotoDetailView(generics.RetrieveDestroyAPIView):
    """View or delete a user photo."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPhotoSerializer
    
    def get_queryset(self):
        return UserPhoto.objects.filter(user=self.request.user)
    
    def perform_destroy(self, instance):
        was_primary = instance.is_primary
        instance.delete()
        
        # If deleted was primary, set first remaining as primary
        if was_primary:
            first_photo = UserPhoto.objects.filter(user=self.request.user).first()
            if first_photo:
                first_photo.is_primary = True
                first_photo.save()


class SetPrimaryPhotoView(APIView):
    """Set a photo as primary profile photo."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            photo = UserPhoto.objects.get(pk=pk, user=request.user)
        except UserPhoto.DoesNotExist:
            return Response(
                {'error': 'Fotoğraf bulunamadı.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Unset current primary
        UserPhoto.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
        
        # Set new primary
        photo.is_primary = True
        photo.save()
        
        # Also update user avatar
        request.user.avatar = photo.image
        request.user.save(update_fields=['avatar'])
        
        return Response({'message': 'Ana fotoğraf güncellendi.'})


class ReorderPhotosView(APIView):
    """Reorder user photos."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = PhotoReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        photo_ids = serializer.validated_data['photo_ids']
        
        # Verify all photos belong to user
        user_photos = UserPhoto.objects.filter(user=request.user, id__in=photo_ids)
        if user_photos.count() != len(photo_ids):
            return Response(
                {'error': 'Geçersiz fotoğraf ID\'leri.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update order
        for index, photo_id in enumerate(photo_ids):
            UserPhoto.objects.filter(id=photo_id).update(order=index)
        
        return Response({'message': 'Fotoğraf sıralaması güncellendi.'})


class UserPhotosPublicView(generics.ListAPIView):
    """View another user's public photos."""
    
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPhotoSerializer
    
    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        return UserPhoto.objects.filter(user_id=user_id)
