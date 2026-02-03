"""
Notification utility functions for sending push notifications.
"""

from firebase_admin.messaging import Message, Notification, MulticastMessage
from fcm_django.models import FCMDevice


def send_notification_to_user(user, title, body, data=None):
    """
    Send push notification to a specific user.
    
    Args:
        user: User instance
        title: Notification title
        body: Notification body text
        data: Optional dict of extra data
    
    Returns:
        Number of successful deliveries
    """
    devices = FCMDevice.objects.filter(user=user, active=True)
    
    if not devices.exists():
        return 0
    
    message = Message(
        notification=Notification(title=title, body=body),
        data=data or {}
    )
    
    try:
        result = devices.send_message(message)
        return len(result.registration_ids_sent) if result else 0
    except Exception as e:
        print(f"Notification error for user {user.id}: {e}")
        return 0


def send_notification_to_users(users, title, body, data=None):
    """
    Send push notification to multiple users.
    
    Args:
        users: QuerySet or list of User instances
        title: Notification title
        body: Notification body text
        data: Optional dict of extra data
    
    Returns:
        Total number of successful deliveries
    """
    total_sent = 0
    
    for user in users:
        total_sent += send_notification_to_user(user, title, body, data)
    
    return total_sent


def send_notification_to_all(title, body, data=None):
    """
    Send push notification to ALL active users with registered devices.
    
    Args:
        title: Notification title
        body: Notification body text
        data: Optional dict of extra data
    
    Returns:
        Number of successful deliveries
    """
    devices = FCMDevice.objects.filter(active=True)
    
    if not devices.exists():
        return 0
    
    message = Message(
        notification=Notification(title=title, body=body),
        data=data or {}
    )
    
    try:
        result = devices.send_message(message)
        return len(result.registration_ids_sent) if result else 0
    except Exception as e:
        print(f"Broadcast notification error: {e}")
        return 0


# ============ Pre-built notification types ============

def notify_new_message(recipient, sender_name, message_preview):
    """Notify user of a new message."""
    return send_notification_to_user(
        user=recipient,
        title=f"💬 {sender_name}",
        body=message_preview[:100],
        data={
            'type': 'new_message',
            'route': '/messages'
        }
    )


def notify_activity_join(activity_creator, participant_name, activity_title):
    """Notify activity creator when someone joins."""
    return send_notification_to_user(
        user=activity_creator,
        title="🎉 Yeni Katılımcı!",
        body=f"{participant_name} '{activity_title}' etkinliğine katıldı.",
        data={
            'type': 'activity_join',
            'route': '/activities'
        }
    )


def notify_activity_cancelled(participants, activity_title):
    """Notify all participants when activity is cancelled."""
    return send_notification_to_users(
        users=participants,
        title="❌ Etkinlik İptal",
        body=f"'{activity_title}' etkinliği iptal edildi.",
        data={
            'type': 'activity_cancelled',
            'route': '/activities'
        }
    )


def notify_activity_reminder(participants, activity_title, time_remaining):
    """Send reminder to participants before activity starts."""
    return send_notification_to_users(
        users=participants,
        title="⏰ Etkinlik Hatırlatması",
        body=f"'{activity_title}' {time_remaining} sonra başlıyor!",
        data={
            'type': 'activity_reminder',
            'route': '/activities'
        }
    )


def notify_new_follower(user, follower_name):
    """Notify user of a new follower."""
    return send_notification_to_user(
        user=user,
        title="👋 Yeni Takipçi!",
        body=f"{follower_name} seni takip etmeye başladı.",
        data={
            'type': 'new_follower',
            'route': '/profile'
        }
    )
