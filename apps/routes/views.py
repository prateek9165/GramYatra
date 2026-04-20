"""
GramYatra — Routes Views
Search routes, today's schedule, ETA, route planner
"""

import logging
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Route, Stop, Schedule
from .serializers import RouteSerializer, RouteListSerializer, ScheduleSerializer
from apps.users.permissions import IsConsumerOrAbove, IsOwnerOrAbove

logger = logging.getLogger('apps.routes')


class RouteSearchView(APIView):
    """
    GET /api/v1/routes/search/?from=Kheda&to=Bhopal
    Search routes by origin and destination.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(
        tags=['routes'],
        summary='Search routes by origin/destination',
        parameters=[
            OpenApiParameter('from', OpenApiTypes.STR, description='Origin location'),
            OpenApiParameter('to',   OpenApiTypes.STR, description='Destination'),
        ]
    )
    def get(self, request):
        from_q = request.query_params.get('from', '').strip()
        to_q   = request.query_params.get('to', '').strip()

        qs = Route.objects.filter(is_active=True).prefetch_related('stops')

        if from_q:
            qs = qs.filter(
                Q(from_location__icontains=from_q) |
                Q(stops__name__icontains=from_q)
            ).distinct()
        if to_q:
            qs = qs.filter(
                Q(to_location__icontains=to_q) |
                Q(stops__name__icontains=to_q)
            ).distinct()

        return Response({
            'count':  qs.count(),
            'routes': RouteSerializer(qs, many=True).data,
        })


class TodayScheduleView(APIView):
    """
    GET /api/v1/routes/schedule/?lat=23.25&lng=77.41
    Returns today's schedule for all active buses, optionally near a location.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['routes'], summary="Get today's bus schedule")
    def get(self, request):
        schedules = (Schedule.objects
                     .filter(is_active=True, vehicle__status='active', vehicle__rto_verified=True)
                     .select_related('vehicle', 'route')
                     .order_by('departure'))

        # Filter to schedules running today
        today_schedules = [s for s in schedules if s.runs_today()]

        now = timezone.localtime().time()
        upcoming = []
        departed = []
        for s in today_schedules:
            item = ScheduleSerializer(s).data
            item['status'] = 'upcoming' if s.departure > now else 'departed'
            (upcoming if s.departure > now else departed).append(item)

        return Response({
            'date':      timezone.localdate().isoformat(),
            'upcoming':  upcoming,
            'departed':  departed,
            'total':     len(today_schedules),
        })


class RouteDetailView(generics.RetrieveAPIView):
    """GET /api/v1/routes/<id>/"""
    queryset           = Route.objects.filter(is_active=True).prefetch_related('stops')
    serializer_class   = RouteSerializer
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['routes'], summary='Get route details with all stops')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RouteListView(generics.ListCreateAPIView):
    """
    GET  /api/v1/routes/  — List all active routes
    POST /api/v1/routes/  — Owner creates a route
    """
    queryset           = Route.objects.filter(is_active=True)
    permission_classes = [IsConsumerOrAbove]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return RouteSerializer
        return RouteListSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsOwnerOrAbove()]
        return [IsConsumerOrAbove()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(tags=['routes'], summary='List all routes')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ScheduleManageView(generics.ListCreateAPIView):
    """
    GET  /api/v1/routes/schedules/          — List schedules (owner sees own)
    POST /api/v1/routes/schedules/          — Owner creates schedule
    """
    serializer_class   = ScheduleSerializer
    permission_classes = [IsOwnerOrAbove]

    def get_queryset(self):
        if self.request.user.is_rto:
            return Schedule.objects.all().select_related('vehicle', 'route')
        return Schedule.objects.filter(
            vehicle__owner=self.request.user
        ).select_related('vehicle', 'route')

    @extend_schema(tags=['routes'], summary='List / create schedules (Owner)')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AIRouteQueryView(APIView):
    """
    GET /api/v1/routes/ai/?q=which+bus+goes+to+Bhopal
    Simple NLP-style route query engine.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['ai'], summary='AI assistant: query buses and routes')
    def get(self, request):
        query = request.query_params.get('q', '').lower().strip()
        if not query:
            return Response({'error': 'Query parameter q is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.tracking.services import get_vehicle_location_cached
        from apps.vehicles.models import Vehicle

        # Extract location keywords from query
        locations = Route.objects.values_list('from_location', 'to_location').distinct()
        all_places = set()
        for f, t in locations:
            all_places.add(f.lower())
            all_places.add(t.lower())

        matched_dest = [p for p in all_places if p in query]

        # Find matching routes and vehicles
        routes_qs = Route.objects.filter(is_active=True)
        if matched_dest:
            routes_qs = routes_qs.filter(
                Q(to_location__icontains=matched_dest[0]) |
                Q(from_location__icontains=matched_dest[0])
            )

        results = []
        for route in routes_qs[:5]:
            vehicles = Vehicle.objects.filter(route=route, status='active')
            for v in vehicles:
                loc = get_vehicle_location_cached(v.id)
                results.append({
                    'bus_code':     v.bus_code,
                    'reg_number':   v.reg_number,
                    'route':        route.name,
                    'from':         route.from_location,
                    'to':           route.to_location,
                    'fare_range':   f'₹{int(route.fare_min)}–₹{int(route.fare_max)}',
                    'current_location': loc,
                    'driver':       v.driver.name if v.driver else 'Unassigned',
                })

        if results:
            response_text = (
                f'Found {len(results)} bus(es) matching your query "{query}". '
                f'The nearest is {results[0]["bus_code"]} on route {results[0]["route"]}.'
            )
        else:
            response_text = (
                f'No buses found for "{query}". '
                'Try searching for a specific destination like "Bhopal" or "Indore".'
            )

        return Response({
            'query':    query,
            'response': response_text,
            'results':  results,
        })
