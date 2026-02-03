"""
Views for moderation app.
"""

from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from activities.models import Activity
from messaging.models import Message
from .models import ReportedContent
from .serializers import CreateReportSerializer

User = get_user_model()


class CreateReportView(APIView):
    """Create a report for inappropriate content."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = CreateReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        report_type = data['report_type']
        
        # Prevent self-reporting
        if report_type == 'user' and data.get('user_id') == request.user.id:
            return Response(
                {'error': 'Kendinizi şikayet edemezsiniz.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get target objects
        reported_user = None
        reported_activity = None
        reported_message = None
        
        if report_type == 'user':
            try:
                reported_user = User.objects.get(id=data['user_id'], is_active=True)
            except User.DoesNotExist:
                return Response(
                    {'error': 'Kullanıcı bulunamadı.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif report_type == 'activity':
            try:
                reported_activity = Activity.objects.get(id=data['activity_id'])
            except Activity.DoesNotExist:
                return Response(
                    {'error': 'Aktivite bulunamadı.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif report_type == 'message':
            try:
                reported_message = Message.objects.get(id=data['message_id'])
                # Verify user is in the conversation
                if not reported_message.conversation.participants.filter(id=request.user.id).exists():
                    return Response(
                        {'error': 'Bu mesajı şikayet etme yetkiniz yok.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Message.DoesNotExist:
                return Response(
                    {'error': 'Mesaj bulunamadı.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Check for duplicate reports
        existing = ReportedContent.objects.filter(
            reporter=request.user,
            report_type=report_type,
            reported_user=reported_user,
            reported_activity=reported_activity,
            reported_message=reported_message,
            status='pending'
        ).exists()
        
        if existing:
            return Response(
                {'message': 'Bu içerik için zaten bekleyen bir şikayetiniz var.'},
                status=status.HTTP_200_OK
            )
        
        # Create report
        report = ReportedContent.objects.create(
            reporter=request.user,
            report_type=report_type,
            reason=data['reason'],
            description=data.get('description', ''),
            reported_user=reported_user,
            reported_activity=reported_activity,
            reported_message=reported_message
        )
        
        # Send notification email to admins
        try:
            admin_email = getattr(settings, 'ADMIN_EMAIL', None)
            if admin_email:
                send_mail(
                    subject=f'[GoDo] Yeni Şikayet: {report.get_reason_display()}',
                    message=f'''
Yeni bir şikayet alındı.

Şikayet Eden: {request.user.email}
Tip: {report.get_report_type_display()}
Sebep: {report.get_reason_display()}
Açıklama: {report.description or 'Yok'}

Admin panelinden inceleyebilirsiniz.
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=True
                )
        except Exception:
            pass
        
        return Response(
            {
                'message': 'Şikayetiniz alındı. En kısa sürede incelenecektir.',
                'report_id': report.id
            },
            status=status.HTTP_201_CREATED
        )
