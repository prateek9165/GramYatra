"""
GramYatra — Vehicles Views
CRUD for vehicles, document upload, nearby search
"""

import math
import logging
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Vehicle, VehicleDocument
from .serializers import (
    VehicleSerializer, VehicleCreateSerializer,
    VehicleListSerializer, NearbyVehicleSerializer,
    VehicleDocumentSerializer
)
from apps.users.permissions import (
    IsConsumerOrAbove, IsOwnerOrAbove, IsRTOOnly, IsOwnerOfObject
)

logger = logging.getLogger('apps.vehicles')


def haversine_km(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two lat/lng points."""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class NearbyVehiclesView(APIView):
    """
    GET /api/v1/vehicles/nearby/?lat=23.25&lng=77.41&radius=15
    Returns active, verified vehicles near a given location
    sorted by distance. Results cached 30s per location cell.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(
        tags=['vehicles'],
        summary='Get nearby active buses',
        parameters=[
            OpenApiParameter('lat',    OpenApiTypes.FLOAT, description='Latitude'),
            OpenApiParameter('lng',    OpenApiTypes.FLOAT, description='Longitude'),
            OpenApiParameter('radius', OpenApiTypes.FLOAT, description='Search radius in km (default 15)'),
        ]
    )
    def get(self, request):
        try:
            lat    = float(request.query_params.get('lat', 0))
            lng    = float(request.query_params.get('lng', 0))
            radius = float(request.query_params.get('radius', 15))
        except (TypeError, ValueError):
            return Response({'error': 'Invalid lat/lng/radius.'}, status=status.HTTP_400_BAD_REQUEST)

        if lat == 0 and lng == 0:
            return Response({'error': 'lat and lng are required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cache key rounded to 0.05° grid (~5km) for reuse
        cache_key = f'nearby:{round(lat,2)}:{round(lng,2)}:{radius}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        from apps.tracking.models import VehicleTracking
        active_vehicles = Vehicle.objects.filter(
            status=Vehicle.Status.ACTIVE,
            rto_verified=True
        ).select_related('route', 'driver')

        results = []
        for vehicle in active_vehicles:
            latest_track = (VehicleTracking.objects
                            .filter(vehicle=vehicle)
                            .order_by('-timestamp')
                            .first())
            if not latest_track:
                continue
            dist = haversine_km(lat, lng,
                                 float(latest_track.lat),
                                 float(latest_track.lng))
            if dist <= radius:
                speed = float(latest_track.speed_kmh) or 30
                eta   = int((dist / speed) * 60)
                vehicle.distance_km = round(dist, 2)
                vehicle.eta_minutes  = eta
                results.append(vehicle)

        results.sort(key=lambda v: v.distance_km)
        data = NearbyVehicleSerializer(results, many=True).data
        cache.set(cache_key, data, timeout=30)
        return Response({'count': len(data), 'vehicles': data})


class VehicleListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/vehicles/        — Owner sees own fleet; RTO sees all
    POST /api/v1/vehicles/        — Owner creates a vehicle (goes to RTO for approval)
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VehicleCreateSerializer
        return VehicleListSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsOwnerOrAbove()]
        return [IsConsumerOrAbove()]

    def get_queryset(self):
        user = self.request.user
        qs   = Vehicle.objects.select_related('route', 'driver', 'owner')
        if user.is_rto:
            return qs.all()
        if user.is_owner:
            return qs.filter(owner=user)
        # Consumer/driver: only active + verified
        return qs.filter(status=Vehicle.Status.ACTIVE, rto_verified=True)

    @extend_schema(tags=['vehicles'], summary='List vehicles')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=['vehicles'], summary='Add new vehicle (Owner)')
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class VehicleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/vehicles/<id>/
    PATCH  /api/v1/vehicles/<id>/   — Owner updates their vehicle
    DELETE /api/v1/vehicles/<id>/   — Owner removes vehicle
    """
    queryset = Vehicle.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return VehicleCreateSerializer
        return VehicleSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsConsumerOrAbove()]
        return [IsOwnerOrAbove(), IsOwnerOfObject()]

    @extend_schema(tags=['vehicles'], summary='Get vehicle details')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VehicleDocumentUploadView(APIView):
    """
    POST /api/v1/vehicles/<id>/documents/
    Owner uploads RC, insurance, fitness etc.
    """
    permission_classes = [IsOwnerOrAbove]
    parser_classes     = [MultiPartParser, FormParser]

    @extend_schema(tags=['vehicles'], summary='Upload vehicle document')
    def post(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, owner=request.user)
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = VehicleDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(vehicle=vehicle)
            logger.info(f'Document uploaded for vehicle {vehicle.reg_number}')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AssignDriverView(APIView):
    """
    POST /api/v1/vehicles/<id>/assign-driver/
    Owner assigns a driver to their vehicle.
    """
    permission_classes = [IsOwnerOrAbove]

    @extend_schema(tags=['vehicles'], summary='Assign driver to vehicle')
    def post(self, request, pk):
        try:
            vehicle = Vehicle.objects.get(pk=pk, owner=request.user)
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)

        driver_id = request.data.get('driver_id')
        if not driver_id:
            return Response({'error': 'driver_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.users.models import User
        try:
            driver = User.objects.get(pk=driver_id, role='driver')
        except User.DoesNotExist:
            return Response({'error': 'Driver not found.'}, status=status.HTTP_404_NOT_FOUND)

        vehicle.driver = driver
        vehicle.save(update_fields=['driver'])
        return Response({'message': f'Driver {driver.name} assigned to {vehicle.bus_code}.'})


class VehicleSearchView(APIView):
    """
    GET /api/v1/vehicles/search/?q=bhopal&type=express
    Full-text search by destination, route, bus code.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['vehicles'], summary='Search vehicles by destination or route')
    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'error': 'Search query q is required.'}, status=status.HTTP_400_BAD_REQUEST)

        vehicles = Vehicle.objects.filter(
            status=Vehicle.Status.ACTIVE,
            rto_verified=True
        ).filter(
            Q(bus_code__icontains=q) |
            Q(reg_number__icontains=q) |
            Q(route__name__icontains=q) |
            Q(route__from_location__icontains=q) |
            Q(route__to_location__icontains=q) |
            Q(route__stops_json__icontains=q)
        ).select_related('route', 'driver')[:20]

        return Response({
            'count': vehicles.count(),
            'results': VehicleListSerializer(vehicles, many=True).data
        })
