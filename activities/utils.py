"""
Utility functions for activities app.
"""

from firebase_admin import messaging


def send_activity_notification(user, title, body, data=None):
    """
    Send push notification to user about activity updates.
    """
    if not user.fcm_token:
        return False
    
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    default_vibrate_timings=True,
                    click_action='FLUTTER_NOTIFICATION_CLICK'
                )
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound='default',
                        badge=1
                    )
                ),
                headers={'apns-priority': '10'}
            ),
            token=user.fcm_token
        )
        
        messaging.send(message)
        return True
    except Exception as e:
        print(f"FCM Error: {e}")
        return False


def mask_location(latitude, longitude, address_full=None):
    """
    Generate masked location display.
    Returns approximate area instead of exact location.
    """
    # Round coordinates to reduce precision
    masked_lat = round(float(latitude), 3)
    masked_lng = round(float(longitude), 3)
    
    # If we have a full address, extract district/neighborhood
    if address_full:
        # Simple extraction - in production, use reverse geocoding
        parts = address_full.split(',')
        if len(parts) >= 2:
            return f"{parts[-2].strip()}, ~500m"
    
    return f"Koordinat ({masked_lat}, {masked_lng}) civarı"


def calculate_distance(lat1, lng1, lat2, lng2):
    """
    Calculate distance between two coordinates in kilometers.
    Uses Haversine formula.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in km
    
    lat1, lng1, lat2, lng2 = map(radians, [float(lat1), float(lng1), float(lat2), float(lng2)])
    
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c
