"""
Serializers for activities app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Activity, ActivityCategory, ActivityParticipation, ActivityImage
from accounts.serializers import UserPublicSerializer

User = get_user_model()


class ActivityCategorySerializer(serializers.ModelSerializer):
    """Serializer for activity categories."""
    
    class Meta:
        model = ActivityCategory
        fields = ['id', 'name', 'name_en', 'icon', 'mode']


class ActivityImageSerializer(serializers.ModelSerializer):
    """Serializer for activity images."""
    
    class Meta:
        model = ActivityImage
        fields = ['id', 'image', 'is_primary', 'order']


class ActivityListSerializer(serializers.ModelSerializer):
    """Serializer for activity list view (limited info)."""
    
    creator = UserPublicSerializer(read_only=True)
    category = ActivityCategorySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()
    spots_left = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    
    class Meta:
        model = Activity
        fields = [
            'id', 'title', 'mode', 'category', 'creator',
            'address_display', 'city', 'district',
            'latitude', 'longitude',
            'start_time', 'end_time',
            'max_participants', 'current_participants', 'spots_left', 'is_full',
            'is_instant', 'is_group_join', 'status',
            'primary_image', 'created_at'
        ]
    
    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first()
        if image:
            return ActivityImageSerializer(image).data
        image = obj.images.first()
        if image:
            return ActivityImageSerializer(image).data
        return None


class ActivityDetailSerializer(serializers.ModelSerializer):
    """Serializer for activity detail view."""
    
    creator = UserPublicSerializer(read_only=True)
    category = ActivityCategorySerializer(read_only=True)
    images = ActivityImageSerializer(many=True, read_only=True)
    spots_left = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    user_participation = serializers.SerializerMethodField()
    show_full_address = serializers.SerializerMethodField()
    
    class Meta:
        model = Activity
        fields = [
            'id', 'title', 'description', 'mode', 'category', 'creator',
            'address_display', 'city', 'district',
            'latitude', 'longitude',
            'start_time', 'end_time',
            'max_participants', 'current_participants', 'spots_left', 'is_full', 'is_past',
            'is_instant', 'is_group_join', 'group_size_min', 'group_size_max',
            'status', 'images',
            'user_participation', 'show_full_address',
            'created_at', 'updated_at'
        ]
    
    def get_user_participation(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            participation = obj.participations.filter(user=request.user).first()
            if participation:
                return ActivityParticipationSerializer(participation).data
        return None
    
    def get_show_full_address(self, obj):
        """Show full address only to approved participants or creator."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Creator always sees full address
            if obj.creator == request.user:
                return obj.address_full
            
            # Approved participants see full address
            participation = obj.participations.filter(
                user=request.user,
                status='approved'
            ).exists()
            
            if participation:
                return obj.address_full
        
        return None


class ActivityCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating activities."""
    
    category_id = serializers.IntegerField(write_only=True)
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Activity
        fields = [
            'title', 'description', 'category_id', 'mode',
            'latitude', 'longitude', 'address_display', 'address_full', 'city', 'district',
            'start_time', 'end_time',
            'max_participants',
            'is_instant', 'is_group_join', 'group_size_min', 'group_size_max',
            'company_domain_filter',
            'is_public_seo',
            'images'
        ]
    
    def validate(self, data):
        # Validate timing
        if data.get('end_time') and data.get('start_time'):
            if data['end_time'] <= data['start_time']:
                raise serializers.ValidationError({
                    'end_time': 'Bitiş zamanı başlangıçtan sonra olmalıdır.'
                })
        
        # Validate group size
        if data.get('is_group_join'):
            if data.get('group_size_min', 1) > data.get('group_size_max', 5):
                raise serializers.ValidationError({
                    'group_size_min': 'Minimum grup boyutu maksimumdan büyük olamaz.'
                })
        
        # Company domain filter only for professional mode
        if data.get('company_domain_filter') and data.get('mode') != 'professional':
            raise serializers.ValidationError({
                'company_domain_filter': 'Şirket filtresi sadece profesyonel modda kullanılabilir.'
            })
        
        return data
    
    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        category_id = validated_data.pop('category_id')
        
        validated_data['category_id'] = category_id
        validated_data['creator'] = self.context['request'].user
        
        activity = Activity.objects.create(**validated_data)
        
        # Create images
        for i, image in enumerate(images_data):
            ActivityImage.objects.create(
                activity=activity,
                image=image,
                is_primary=(i == 0),
                order=i
            )
        
        return activity


class ActivityUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating activities."""
    
    class Meta:
        model = Activity
        fields = [
            'title', 'description',
            'address_display', 'address_full',
            'start_time', 'end_time',
            'max_participants',
            'status', 'is_active'
        ]


class ActivityParticipationSerializer(serializers.ModelSerializer):
    """Serializer for participation records."""
    
    user = UserPublicSerializer(read_only=True)
    
    class Meta:
        model = ActivityParticipation
        fields = [
            'id', 'user', 'status', 'message',
            'is_group', 'group_member_count', 'group_members_info',
            'applied_at', 'responded_at'
        ]


class ApplyToActivitySerializer(serializers.Serializer):
    """Serializer for applying to an activity."""
    
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    is_group = serializers.BooleanField(default=False)
    group_member_count = serializers.IntegerField(min_value=1, max_value=10, default=1)
    group_members_info = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )


class ParticipationResponseSerializer(serializers.Serializer):
    """Serializer for responding to participation requests."""
    
    action = serializers.ChoiceField(choices=['approve', 'reject'])
