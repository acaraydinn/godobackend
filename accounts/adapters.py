"""
Custom Social Account Adapter for GoDo.
Handles Google Sign-In profile data extraction.
"""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
import requests


class GodoSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to populate user profile from Google Sign-In data.
    Extracts display_name and avatar from Google account.
    """
    
    def populate_user(self, request, sociallogin: SocialLogin, data: dict):
        """
        Populate user instance with Google profile data.
        Called when a new user signs up via social login.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Get extra data from Google
        extra_data = sociallogin.account.extra_data
        
        # Set display name from Google
        if not user.display_name:
            # Try full name first, then individual parts
            name = extra_data.get('name')
            if not name:
                first_name = extra_data.get('given_name', '')
                last_name = extra_data.get('family_name', '')
                name = f"{first_name} {last_name}".strip()
            
            if name:
                user.display_name = name
        
        return user
    
    def save_user(self, request, sociallogin: SocialLogin, form=None):
        """
        Save the user and download their Google profile picture.
        """
        user = super().save_user(request, sociallogin, form)
        
        # Get extra data from Google
        extra_data = sociallogin.account.extra_data
        
        # Download and save Google profile picture
        picture_url = extra_data.get('picture')
        if picture_url and not user.avatar:
            try:
                self._save_avatar_from_url(user, picture_url)
            except Exception:
                pass  # Don't fail if avatar download fails
        
        return user
    
    def _save_avatar_from_url(self, user, url):
        """
        Download image from URL and save as user avatar.
        """
        from django.core.files.base import ContentFile
        import hashlib
        
        # Download the image
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # Generate filename from URL hash
            filename = f"google_{hashlib.md5(url.encode()).hexdigest()[:10]}.jpg"
            
            # Save to user's avatar field
            user.avatar.save(filename, ContentFile(response.content), save=True)
