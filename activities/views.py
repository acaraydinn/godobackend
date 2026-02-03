"""
Views for activities app.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend

from accounts.models import BlockedUser
from moderation.utils import filter_ugc_content
from .models import Activity, ActivityCategory, ActivityParticipation
from .serializers import (
    ActivityListSerializer, ActivityDetailSerializer, ActivityCreateSerializer,
    ActivityUpdateSerializer, ActivityCategorySerializer,
    ActivityParticipationSerializer, ApplyToActivitySerializer,
    ParticipationResponseSerializer
)
from .utils import send_activity_notification


class ActivityCategoryListView(generics.ListAPIView):
    """List all activity categories."""
    
    permission_classes = [permissions.AllowAny]
    serializer_class = ActivityCategorySerializer
    
    def get_queryset(self):
        queryset = ActivityCategory.objects.filter(is_active=True)
        
        # Filter by mode if provided
        mode = self.request.query_params.get('mode')
        if mode:
            queryset = queryset.filter(Q(mode=mode) | Q(mode='both'))
        
        return queryset


class ActivityViewSet(ModelViewSet):
    """ViewSet for activities CRUD."""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['mode', 'category', 'status', 'city', 'is_instant', 'is_group_join', 'creator']
    search_fields = ['title', 'description']
    ordering_fields = ['start_time', 'created_at', 'current_participants']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        now = timezone.now()
        
        # Filter active and not expired activities (start_time in future)
        queryset = Activity.objects.filter(is_active=True, start_time__gte=now)
        
        # Exclude activities from blocked users
        blocked_ids = BlockedUser.objects.filter(
            blocker=user
        ).values_list('blocked_id', flat=True)
        queryset = queryset.exclude(creator_id__in=blocked_ids)
        
        # Exclude users who blocked current user
        blocked_by_ids = BlockedUser.objects.filter(
            blocked=user
        ).values_list('blocker_id', flat=True)
        queryset = queryset.exclude(creator_id__in=blocked_by_ids)
        
        # Filter by mode
        mode = self.request.query_params.get('mode')
        if mode:
            queryset = queryset.filter(mode=mode)
        
        # Professional mode: Filter by company domain if applicable
        company_only = self.request.query_params.get('company_only')
        if company_only == 'true' and user.is_verified_company:
            queryset = queryset.filter(
                Q(company_domain_filter__isnull=True) |
                Q(company_domain_filter='') |
                Q(company_domain_filter=user.company_domain)
            )
        
        # Filter upcoming activities
        upcoming = self.request.query_params.get('upcoming')
        if upcoming == 'true':
            queryset = queryset.filter(start_time__gte=timezone.now())
        
        # Filter instant plans
        instant = self.request.query_params.get('instant')
        if instant == 'true':
            queryset = queryset.filter(is_instant=True)
        
        # Location filter (within radius)
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 10)  # km
        
        if lat and lng:
            # Simple bounding box filter (for proper distance, use PostGIS)
            lat = float(lat)
            lng = float(lng)
            radius = float(radius)
            
            # Approximate degrees for km
            lat_range = radius / 111
            lng_range = radius / (111 * abs(lat) if lat != 0 else 111)
            
            queryset = queryset.filter(
                latitude__gte=lat - lat_range,
                latitude__lte=lat + lat_range,
                longitude__gte=lng - lng_range,
                longitude__lte=lng + lng_range
            )
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ActivityListSerializer
        elif self.action == 'retrieve':
            return ActivityDetailSerializer
        elif self.action == 'create':
            return ActivityCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ActivityUpdateSerializer
        return ActivityListSerializer
    
    def perform_create(self, serializer):
        # Filter UGC content
        title = serializer.validated_data.get('title', '')
        description = serializer.validated_data.get('description', '')
        
        title_result = filter_ugc_content(title)
        desc_result = filter_ugc_content(description)
        
        if not title_result['is_clean'] or not desc_result['is_clean']:
            from rest_framework.exceptions import ValidationError
            violations = title_result.get('violations', []) + desc_result.get('violations', [])
            raise ValidationError({
                'detail': 'İçeriğiniz uygunsuz ifadeler içeriyor.',
                'violations': violations
            })
        
        serializer.save(creator=self.request.user)
    
    def perform_destroy(self, instance):
        # Soft delete
        instance.is_active = False
        instance.save()
    
    @action(detail=False, methods=['get'])
    def my_activities(self, request):
        """Get ALL activities created by current user (including past ones)."""
        queryset = Activity.objects.filter(
            creator=request.user,
            is_active=True
        ).order_by('-start_time')
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='user/(?P<user_id>[^/.]+)')
    def user_activities(self, request, user_id=None):
        """Get activities created by another user (only future activities visible)."""
        now = timezone.now()
        queryset = Activity.objects.filter(
            creator_id=user_id,
            is_active=True,
            start_time__gte=now
        ).order_by('start_time')
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def joined(self, request):
        """Get activities user has joined (only future activities)."""
        now = timezone.now()
        participation_ids = ActivityParticipation.objects.filter(
            user=request.user,
            status='approved'
        ).values_list('activity_id', flat=True)
        
        queryset = Activity.objects.filter(
            id__in=participation_ids,
            start_time__gte=now,
            is_active=True
        ).order_by('start_time')
        serializer = ActivityListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply to join an activity."""
        activity = self.get_object()
        
        # Check if already applied
        if ActivityParticipation.objects.filter(activity=activity, user=request.user).exists():
            return Response(
                {'error': 'Bu aktiviteye zaten başvurdunuz.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if creator
        if activity.creator == request.user:
            return Response(
                {'error': 'Kendi aktivitenize başvuramazsınız.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if activity is full
        if activity.is_full:
            return Response(
                {'error': 'Bu aktivite dolu.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check company domain filter
        if activity.company_domain_filter:
            if not request.user.is_verified_company or request.user.company_domain != activity.company_domain_filter:
                return Response(
                    {'error': 'Bu aktivite sadece belirli şirket çalışanlarına açık.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        serializer = ApplyToActivitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Filter message content
        message = serializer.validated_data.get('message', '')
        if message:
            msg_result = filter_ugc_content(message)
            if not msg_result['is_clean']:
                return Response(
                    {'error': 'Mesajınız uygunsuz ifadeler içeriyor.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        participation = ActivityParticipation.objects.create(
            activity=activity,
            user=request.user,
            message=message,
            is_group=serializer.validated_data.get('is_group', False),
            group_member_count=serializer.validated_data.get('group_member_count', 1),
            group_members_info=serializer.validated_data.get('group_members_info', [])
        )
        
        # Notify activity creator
        send_activity_notification(
            activity.creator,
            'Yeni Başvuru',
            f'{request.user.display_name or request.user.email} aktivitenize başvurdu.',
            {'activity_id': activity.id, 'participation_id': participation.id}
        )
        
        return Response(
            ActivityParticipationSerializer(participation).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def applications(self, request, pk=None):
        """Get applications for an activity (creator only)."""
        activity = self.get_object()
        
        if activity.creator != request.user:
            return Response(
                {'error': 'Bu işlem için yetkiniz yok.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        participations = activity.participations.all()
        serializer = ActivityParticipationSerializer(participations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='applications/(?P<participation_id>[^/.]+)/respond')
    def respond_to_application(self, request, pk=None, participation_id=None):
        """Approve or reject an application (creator only)."""
        activity = self.get_object()
        
        if activity.creator != request.user:
            return Response(
                {'error': 'Bu işlem için yetkiniz yok.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            participation = activity.participations.get(id=participation_id)
        except ActivityParticipation.DoesNotExist:
            return Response(
                {'error': 'Başvuru bulunamadı.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ParticipationResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action = serializer.validated_data['action']
        
        if action == 'approve':
            # Check capacity
            if activity.spots_left < participation.group_member_count:
                return Response(
                    {'error': 'Yeterli kontenjan yok.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            participation.approve()
            message = 'Başvurunuz onaylandı!'
        else:
            participation.reject()
            message = 'Başvurunuz reddedildi.'
        
        # Notify applicant
        send_activity_notification(
            participation.user,
            'Başvuru Durumu',
            message,
            {'activity_id': activity.id}
        )
        
        return Response(ActivityParticipationSerializer(participation).data)


class PublicActivityDetailView(generics.RetrieveAPIView):
    """
    Public activity detail for SEO pages.
    Only shows activities marked as public.
    """
    
    permission_classes = [permissions.AllowAny]
    serializer_class = ActivityDetailSerializer
    lookup_field = 'seo_slug'
    
    def get_queryset(self):
        return Activity.objects.filter(is_public_seo=True, is_active=True)
