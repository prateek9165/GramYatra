"""
GramYatra — Vehicles Serializers
"""

from rest_framework import serializers
from .models import Vehicle, VehicleDocument
from apps.users.serializers import UserListSerializer


class VehicleDocumentSerializer(serializers.ModelSerializer):
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model  = VehicleDocument
        fields = ['id', 'doc_type', 'document', 'expiry_date',
                  'is_verified', 'is_expired', 'uploaded_at']
        read_only_fields = ['is_verified', 'uploaded_at']


class VehicleSerializer(serializers.ModelSerializer):
    documents      = VehicleDocumentSerializer(many=True, read_only=True)
    owner_name     = serializers.CharField(source='owner.name', read_only=True)
    driver_name    = serializers.CharField(source='driver.name', read_only=True)
    route_name     = serializers.CharField(source='route.name', read_only=True)
    is_active      = serializers.ReadOnlyField()
    current_location = serializers.SerializerMethodField()

    class Meta:
        model  = Vehicle
        fields = [
            'id', 'reg_number', 'bus_code', 'model_name', 'vehicle_type',
            'capacity', 'manufacture_year', 'status', 'rto_verified',
            'rto_verified_at', 'rejection_reason', 'route', 'route_name',
            'owner', 'owner_name', 'driver', 'driver_name',
            'documents', 'is_active', 'current_location',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['rto_verified', 'rto_verified_at', 'status', 'created_at', 'updated_at']

    def get_current_location(self, obj):
        """Return the latest tracking point for this vehicle."""
        from apps.tracking.models import VehicleTracking
        latest = VehicleTracking.objects.filter(vehicle=obj).order_by('-timestamp').first()
        if latest:
            return {
                'lat': float(latest.lat),
                'lng': float(latest.lng),
                'speed_kmh': float(latest.speed_kmh),
                'accuracy_m': latest.accuracy_m,
                'timestamp': latest.timestamp,
            }
        return None


class VehicleCreateSerializer(serializers.ModelSerializer):
    """Used by owners to create a new vehicle."""
    class Meta:
        model  = Vehicle
        fields = ['reg_number', 'model_name', 'vehicle_type', 'capacity',
                  'manufacture_year', 'route']

    def validate_reg_number(self, value):
        value = value.upper().replace(' ', '')
        if Vehicle.objects.filter(reg_number=value).exists():
            raise serializers.ValidationError('This registration number is already registered.')
        return value

    def create(self, validated_data):
        validated_data['owner']  = self.context['request'].user
        validated_data['status'] = Vehicle.Status.PENDING
        return super().create(validated_data)


class VehicleListSerializer(serializers.ModelSerializer):
    """Lightweight for map/list views."""
    current_location = serializers.SerializerMethodField()
    route_name       = serializers.CharField(source='route.name', read_only=True)
    driver_name      = serializers.CharField(source='driver.name', read_only=True)

    class Meta:
        model  = Vehicle
        fields = ['id', 'bus_code', 'reg_number', 'model_name', 'vehicle_type',
                  'capacity', 'status', 'route_name', 'driver_name', 'current_location']

    def get_current_location(self, obj):
        from apps.tracking.models import VehicleTracking
        latest = VehicleTracking.objects.filter(vehicle=obj).order_by('-timestamp').first()
        if latest:
            return {'lat': float(latest.lat), 'lng': float(latest.lng),
                    'speed_kmh': float(latest.speed_kmh), 'timestamp': latest.timestamp}
        return None


class NearbyVehicleSerializer(serializers.ModelSerializer):
    """Vehicle with distance and ETA for consumer map view."""
    distance_km    = serializers.FloatField(read_only=True)
    eta_minutes    = serializers.IntegerField(read_only=True)
    current_location = serializers.SerializerMethodField()
    route_name     = serializers.CharField(source='route.name', read_only=True)
    driver_name    = serializers.CharField(source='driver.name', read_only=True)

    class Meta:
        model  = Vehicle
        fields = ['id', 'bus_code', 'reg_number', 'model_name', 'capacity',
                  'status', 'route_name', 'driver_name',
                  'distance_km', 'eta_minutes', 'current_location']

    def get_current_location(self, obj):
        from apps.tracking.models import VehicleTracking
        latest = VehicleTracking.objects.filter(vehicle=obj).order_by('-timestamp').first()
        if latest:
            return {'lat': float(latest.lat), 'lng': float(latest.lng),
                    'speed_kmh': float(latest.speed_kmh), 'timestamp': latest.timestamp}
        return None
