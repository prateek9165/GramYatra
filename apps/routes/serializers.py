"""
GramYatra — Routes Serializers
"""

from rest_framework import serializers
from .models import Route, Stop, Schedule


class StopSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Stop
        fields = ['id', 'name', 'order', 'lat', 'lng', 'distance_from_start_km']


class RouteSerializer(serializers.ModelSerializer):
    stops = StopSerializer(many=True, read_only=True)

    class Meta:
        model  = Route
        fields = ['id', 'name', 'from_location', 'to_location', 'distance_km',
                  'fare_min', 'fare_max', 'is_active', 'stops']


class RouteListSerializer(serializers.ModelSerializer):
    stop_count = serializers.IntegerField(source='stops.count', read_only=True)

    class Meta:
        model  = Route
        fields = ['id', 'name', 'from_location', 'to_location',
                  'distance_km', 'fare_min', 'fare_max', 'stop_count']


class ScheduleSerializer(serializers.ModelSerializer):
    vehicle_code = serializers.CharField(source='vehicle.bus_code',   read_only=True)
    route_name   = serializers.CharField(source='route.name',         read_only=True)
    from_loc     = serializers.CharField(source='route.from_location', read_only=True)
    to_loc       = serializers.CharField(source='route.to_location',   read_only=True)
    runs_today   = serializers.ReadOnlyField()

    class Meta:
        model  = Schedule
        fields = ['id', 'vehicle', 'vehicle_code', 'route', 'route_name',
                  'from_loc', 'to_loc', 'departure', 'arrival', 'days',
                  'is_active', 'runs_today']
