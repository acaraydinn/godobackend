"""
UGC (User Generated Content) filtering utilities.
Provides content moderation for App Store compliance.
"""

import re
from better_profanity import profanity

# Initialize profanity filter with custom words
profanity.load_censor_words()

# Phone number patterns
PHONE_PATTERNS = [
    r'\+?90?\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # Turkish phone
    r'\+?\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # International
    r'\d{10,11}',  # Simple 10-11 digit
    r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (XXX) XXX-XXXX
]

# Email pattern
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Social media handles
SOCIAL_PATTERNS = [
    r'@[a-zA-Z0-9_]{3,}',  # @username
    r'instagram\.com/[a-zA-Z0-9_]+',
    r'twitter\.com/[a-zA-Z0-9_]+',
    r'facebook\.com/[a-zA-Z0-9.]+',
    r't\.me/[a-zA-Z0-9_]+',  # Telegram
]

# Banned keywords (Turkish + English)
BANNED_KEYWORDS = [
    # Add your banned keywords here
    # These will be loaded from database if available
]


def filter_ugc_content(text: str) -> dict:
    """
    Filter user-generated content for inappropriate material.
    
    Returns:
        {
            'filtered_text': str,  # Sanitized content
            'original_text': str,  # Original for logging
            'is_clean': bool,      # Pass/fail
            'violations': list     # List of detected issues
        }
    """
    if not text:
        return {
            'filtered_text': '',
            'original_text': '',
            'is_clean': True,
            'violations': []
        }
    
    original = text
    filtered = text
    violations = []
    
    # 1. Check for phone numbers
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, filtered)
        if matches:
            violations.append({'type': 'phone_number', 'matches': matches})
            filtered = re.sub(pattern, '[telefon gizlendi]', filtered)
    
    # 2. Check for email addresses
    email_matches = re.findall(EMAIL_PATTERN, filtered, re.IGNORECASE)
    if email_matches:
        violations.append({'type': 'email', 'matches': email_matches})
        filtered = re.sub(EMAIL_PATTERN, '[email gizlendi]', filtered, flags=re.IGNORECASE)
    
    # 3. Check for social media handles
    for pattern in SOCIAL_PATTERNS:
        matches = re.findall(pattern, filtered, re.IGNORECASE)
        if matches:
            violations.append({'type': 'social_media', 'matches': matches})
            filtered = re.sub(pattern, '[sosyal medya gizlendi]', filtered, flags=re.IGNORECASE)
    
    # 4. Check for profanity
    if profanity.contains_profanity(filtered):
        violations.append({'type': 'profanity', 'matches': []})
        filtered = profanity.censor(filtered)
    
    # 5. Check banned keywords from database
    try:
        from .models import BannedWord
        banned_words = BannedWord.objects.filter(is_active=True).values_list('word', 'is_regex')
        
        for word, is_regex in banned_words:
            if is_regex:
                if re.search(word, filtered, re.IGNORECASE):
                    violations.append({'type': 'banned_word', 'matches': [word]})
                    filtered = re.sub(word, '[içerik gizlendi]', filtered, flags=re.IGNORECASE)
            else:
                if word.lower() in filtered.lower():
                    violations.append({'type': 'banned_word', 'matches': [word]})
                    # Case-insensitive replace
                    pattern = re.compile(re.escape(word), re.IGNORECASE)
                    filtered = pattern.sub('[içerik gizlendi]', filtered)
    except Exception:
        pass  # Database not available yet
    
    return {
        'filtered_text': filtered,
        'original_text': original,
        'is_clean': len(violations) == 0,
        'violations': violations
    }


def is_content_safe(text: str) -> bool:
    """
    Quick check if content passes moderation.
    """
    result = filter_ugc_content(text)
    return result['is_clean']


def get_violation_message(violations: list) -> str:
    """
    Generate user-friendly message for violations.
    """
    if not violations:
        return ''
    
    messages = []
    
    for v in violations:
        if v['type'] == 'phone_number':
            messages.append('Telefon numarası paylaşımı yasaktır.')
        elif v['type'] == 'email':
            messages.append('E-posta adresi paylaşımı yasaktır.')
        elif v['type'] == 'social_media':
            messages.append('Sosyal medya hesabı paylaşımı yasaktır.')
        elif v['type'] == 'profanity':
            messages.append('Uygunsuz dil kullanımı tespit edildi.')
        elif v['type'] == 'banned_word':
            messages.append('Yasaklı içerik tespit edildi.')
    
    return ' '.join(set(messages))
