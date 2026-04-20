"""
GramYatra — Tracking REST Views

POST /api/v1/tracking/update/       — Driver posts cell-tower readings
GET  /api/v1/tracking/<id>/live/    — Get latest position of a vehicle
GET  /api/v1/tracking/<id>/history/ — Location history (RTO/owner)
GET  /api/v1/tracking/towers/       — List nearby cell towers
"""

import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import VehicleTracking, CellTower
from .services import triangulate, get_vehicle_location_cached, calculate_eta_minutes
from apps.users.permissions import IsDriverOrAbove, IsConsumerOrAbove, IsRTOOnly, IsOwnerOrAbove
from apps.vehicles.models import Vehicle

logger = logging.getLogger('apps.tracking')


class LocationUpdateView(APIView):
    """
    POST /api/v1/tracking/update/
    Driver (or system) posts cell tower readings.
    Server triangulates → stores → broadcasts via WebSocket.

    Request body:
    {
        "vehicle_id": 1,
        "towers": [
            {"tower_code": "TOWER-A1042", "rssi": -82},
            {"tower_code": "TOWER-B2087", "rssi": -94},
            {"tower_code": "TOWER-C3014", "rssi": -101}
        ],
        "gps_lat": 23.2599,    // optional
        "gps_lng": 77.4126,    // optional
        "speed_kmh": 45,
        "bearing": 270
    }
    """
    permission_classes = [IsDriverOrAbove]

    @extend_schema(tags=['tracking'], summary='Driver posts cell-tower location update')
    def post(self, request):
        vehicle_id = request.data.get('vehicle_id')
        towers     = request.data.get('towers', [])

        if not vehicle_id:
            return Response({'error': 'vehicle_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(towers) < 1:
            return Response({'error': 'At least 1 tower reading required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify vehicle exists and driver is assigned
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id, status='active')
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found or inactive.'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.is_driver and vehicle.driver_id != request.user.id:
            return Response({'error': 'You are not assigned to this vehicle.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            result = triangulate(towers)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve tower FKs
        tower_details = result.get('tower_details', [])
        def get_tower(idx):
            if idx < len(tower_details):
                return CellTower.objects.filter(tower_code=tower_details[idx]['code']).first()
            return None
        def get_rssi(idx):
            if idx < len(tower_details):
                return tower_details[idx]['rssi']
            return -100

        tracking = VehicleTracking.objects.create(
            vehicle     = vehicle,
            lat         = result['lat'],
            lng         = result['lng'],
            accuracy_m  = result['accuracy_m'],
            speed_kmh   = request.data.get('speed_kmh', 0),
            bearing_deg = request.data.get('bearing', 0),
            tower1      = get_tower(0), tower1_rssi = get_rssi(0),
            tower2      = get_tower(1), tower2_rssi = get_rssi(1),
            tower3      = get_tower(2), tower3_rssi = get_rssi(2),
            gps_lat     = request.data.get('gps_lat'),
            gps_lng     = request.data.get('gps_lng'),
            gps_used    = bool(request.data.get('gps_lat')),
        )

        # Push to WebSocket subscribers via channel layer
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        location_data = {
            'lat':        result['lat'],
            'lng':        result['lng'],
            'accuracy_m': result['accuracy_m'],
            'speed_kmh':  float(request.data.get('speed_kmh', 0)),
            'bearing':    float(request.data.get('bearing', 0)),
            'timestamp':  tracking.timestamp.isoformat(),
            'gps_used':   tracking.gps_used,
        }
        # Broadcast to vehicle-specific group and all-vehicles RTO group
        for group in [f'vehicle_{vehicle_id}', 'all_vehicles']:
            async_to_sync(channel_layer.group_send)(group, {
                'type': 'broadcast_location',
                'vehicle': vehicle_id,
                'data': location_data,
            })

        logger.info(f'Location updated: vehicle {vehicle.bus_code} → ({result["lat"]}, {result["lng"]})')

        return Response({
            'message': 'Location updated.',
            'triangulation': result,
            'tracking_id': tracking.id,
        }, status=status.HTTP_201_CREATED)


class LiveLocationView(APIView):
    """
    GET /api/v1/tracking/<vehicle_id>/live/
    Returns the latest triangulated position of a vehicle.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['tracking'], summary='Get live location of a vehicle')
    def get(self, request, vehicle_id):
        location = get_vehicle_location_cached(vehicle_id)
        if not location:
            return Response({'error': 'No tracking data available for this vehicle.'},
                            status=status.HTTP_404_NOT_FOUND)

        # Calculate ETA to user's location if provided
        user_lat = request.query_params.get('user_lat')
        user_lng = request.query_params.get('user_lng')
        if user_lat and user_lng:
            try:
                eta = calculate_eta_minutes(
                    location['lat'], location['lng'],
                    float(user_lat), float(user_lng),
                    location.get('speed_kmh', 30)
                )
                location['eta_minutes'] = eta
            except (ValueError, TypeError):
                pass

        return Response({'vehicle_id': vehicle_id, 'location': location})


class LocationHistoryView(APIView):
    """
    GET /api/v1/tracking/<vehicle_id>/history/?from=2024-01-01&to=2024-01-02
    Returns paginated history. Owner sees own vehicles; RTO sees all.
    """
    permission_classes = [IsOwnerOrAbove]

    @extend_schema(
        tags=['tracking'],
        summary='Get vehicle location history (Owner/RTO)',
        parameters=[
            OpenApiParameter('from', OpenApiTypes.DATETIME, description='Start datetime (ISO)'),
            OpenApiParameter('to',   OpenApiTypes.DATETIME, description='End datetime (ISO)'),
        ]
    )
    def get(self, request, vehicle_id):
        try:
            if request.user.is_owner:
                vehicle = Vehicle.objects.get(pk=vehicle_id, owner=request.user)
            else:
                vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)

        qs = VehicleTracking.objects.filter(vehicle=vehicle).order_by('-timestamp')

        from_dt = request.query_params.get('from')
        to_dt   = request.query_params.get('to')
        if from_dt:
            qs = qs.filter(timestamp__gte=from_dt)
        if to_dt:
            qs = qs.filter(timestamp__lte=to_dt)

        # Limit to 1000 points max
        qs = qs[:1000]

        data = [
            {
                'lat':        float(t.lat),
                'lng':        float(t.lng),
                'speed_kmh':  float(t.speed_kmh),
                'bearing':    float(t.bearing_deg),
                'accuracy_m': t.accuracy_m,
                'gps_used':   t.gps_used,
                'timestamp':  t.timestamp.isoformat(),
            }
            for t in qs
        ]
        return Response({'vehicle_id': vehicle_id, 'count': len(data), 'history': data})


class NearbyTowersView(APIView):
    """
    GET /api/v1/tracking/towers/?lat=23.25&lng=77.41&radius=5
    Returns cell towers near a location (for driver diagnostics).
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['tracking'], summary='List nearby cell towers')
    def get(self, request):
        try:
            lat    = float(request.query_params.get('lat', 0))
            lng    = float(request.query_params.get('lng', 0))
            radius = float(request.query_params.get('radius', 5))
        except (TypeError, ValueError):
            return Response({'error': 'Invalid parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        import math
        towers = CellTower.objects.filter(is_active=True)
        result = []
        for t in towers:
            R = 6371
            d_lat = math.radians(float(t.lat) - lat)
            d_lng = math.radians(float(t.lng) - lng)
            a = (math.sin(d_lat/2)**2 +
                 math.cos(math.radians(lat)) * math.cos(math.radians(float(t.lat))) *
                 math.sin(d_lng/2)**2)
            dist_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            if dist_km <= radius:
                result.append({
                    'tower_code':    t.tower_code,
                    'operator':      t.operator,
                    'lat':           float(t.lat),
                    'lng':           float(t.lng),
                    'technology':    t.technology,
                    'coverage_m':    t.coverage_radius_m,
                    'distance_km':   round(dist_km, 3),
                })
        result.sort(key=lambda x: x['distance_km'])
        return Response({'count': len(result), 'towers': result})
