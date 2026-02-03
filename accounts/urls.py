"""
URL patterns for accounts app.
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # User Profile
    path('users/me/', views.CurrentUserView.as_view(), name='current-user'),
    path('users/me/privacy/', views.PrivacySettingsView.as_view(), name='privacy-settings'),
    path('users/me/delete/', views.AccountDeleteView.as_view(), name='account-delete'),
    path('users/me/fcm-token/', views.UpdateFCMTokenView.as_view(), name='update-fcm-token'),
    path('users/me/test-notification/', views.SendTestNotificationView.as_view(), name='test-notification'),
    path('users/<int:pk>/', views.UserPublicProfileView.as_view(), name='user-profile'),
    
    # User Photos
    path('users/me/photos/', views.UserPhotoListCreateView.as_view(), name='user-photos'),
    path('users/me/photos/<int:pk>/', views.UserPhotoDetailView.as_view(), name='user-photo-detail'),
    path('users/me/photos/<int:pk>/set-primary/', views.SetPrimaryPhotoView.as_view(), name='set-primary-photo'),
    path('users/me/photos/reorder/', views.ReorderPhotosView.as_view(), name='reorder-photos'),
    path('users/<int:user_id>/photos/', views.UserPhotosPublicView.as_view(), name='user-photos-public'),
    
    # Blocking
    path('users/blocked/', views.BlockedUsersListView.as_view(), name='blocked-users'),
    path('users/<int:user_id>/block/', views.BlockUserView.as_view(), name='block-user'),
    
    # Company Verification
    path('verify-company/', views.VerifyCompanyEmailView.as_view(), name='verify-company'),
    
    # Two-Factor Authentication
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa-setup'),
    path('2fa/verify/', views.TwoFactorVerifyView.as_view(), name='2fa-verify'),
    
    # Legal Documents
    path('contracts/', views.LegalDocumentListView.as_view(), name='legal-documents'),
    path('contracts/<slug:slug>/', views.LegalDocumentView.as_view(), name='legal-document'),
]
