"""
Serializers for moderation app.
"""

from rest_framework import serializers
from .models import ReportedContent


class CreateReportSerializer(serializers.Serializer):
    """Serializer for creating a report."""
    
    REPORT_TYPE_CHOICES = ['activity', 'user', 'message']
    REASON_CHOICES = [
        'spam', 'inappropriate', 'harassment', 'hate_speech',
        'violence', 'scam', 'fake_profile', 'other'
    ]
    
    report_type = serializers.ChoiceField(choices=REPORT_TYPE_CHOICES)
    reason = serializers.ChoiceField(choices=REASON_CHOICES)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    
    # Target IDs (only one should be provided based on report_type)
    user_id = serializers.IntegerField(required=False)
    activity_id = serializers.IntegerField(required=False)
    message_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        report_type = data.get('report_type')
        
        if report_type == 'user' and not data.get('user_id'):
            raise serializers.ValidationError({'user_id': 'Kullanıcı ID gerekli.'})
        elif report_type == 'activity' and not data.get('activity_id'):
            raise serializers.ValidationError({'activity_id': 'Aktivite ID gerekli.'})
        elif report_type == 'message' and not data.get('message_id'):
            raise serializers.ValidationError({'message_id': 'Mesaj ID gerekli.'})
        
        return data


class ReportedContentSerializer(serializers.ModelSerializer):
    """Serializer for viewing reports (admin)."""
    
    reporter_email = serializers.CharField(source='reporter.email', read_only=True)
    
    class Meta:
        model = ReportedContent
        fields = [
            'id', 'reporter_email', 'report_type', 'reason', 'description',
            'status', 'created_at'
        ]
