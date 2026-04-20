"""
GramYatra — RTO Views
Full verification pipeline, compliance monitoring, audit log,
dashboard stats, and cross-interface access.
"""

import logging
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import VerificationRecord, ComplianceFlag, RTOAuditLog
from .serializers import (
    VerificationRecordSerializer, ComplianceFlagSerializer,
    RTOAuditLogSerializer, RTODashboardSerializer
)
from apps.users.permissions import IsRTOOnly, IsConsumerOrAbove
from apps.vehicles.models import Vehicle, VehicleDocument
from apps.users.models import User

logger = logging.getLogger('apps.rto')


def log_rto_action(officer, action, target_type='', target_id=None,
                   detail='', ip_address=None):
    """Helper to write an immutable audit log entry."""
    RTOAuditLog.objects.create(
        officer=officer, action=action,
        target_type=target_type, target_id=target_id,
        detail=detail, ip_address=ip_address
    )


class RTODashboardView(APIView):
    """
    GET /api/v1/rto/dashboard/
    System-wide stats for the RTO officer homepage.
    """
    permission_classes = [IsRTOOnly]

    @extend_schema(tags=['rto'], summary='RTO dashboard statistics')
    def get(self, request):
        from apps.tracking.models import VehicleTracking
        from apps.notifications.models import SMSLog, EmergencyAlert
        from apps.routes.models import Route
        from django.utils import timezone

        one_min_ago = timezone.now() - timezone.timedelta(minutes=5)

        # Active buses = vehicles that sent a tracking ping in the last 5 min
        active_vehicle_ids = (VehicleTracking.objects
                               .filter(timestamp__gte=one_min_ago)
                               .values_list('vehicle_id', flat=True)
                               .distinct())

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

        stats = {
            'total_vehicles':       Vehicle.objects.count(),
            'pending_vehicles':     Vehicle.objects.filter(status='pending').count(),
            'approved_vehicles':    Vehicle.objects.filter(status='active').count(),
            'rejected_vehicles':    Vehicle.objects.filter(status='rejected').count(),
            'flagged_vehicles':     Vehicle.objects.filter(status='flagged').count(),
            'total_drivers':        User.objects.filter(role='driver').count(),
            'pending_drivers':      User.objects.filter(
                                        role='driver',
                                        driver_profile__is_rto_verified=False
                                    ).count(),
            'total_routes':         Route.objects.filter(is_active=True).count(),
            'active_buses_now':     len(active_vehicle_ids),
            'open_compliance_flags': ComplianceFlag.objects.filter(status='open').count(),
            'sms_today':            SMSLog.objects.filter(sent_at__gte=today_start).count(),
            'emergencies_active':   EmergencyAlert.objects.filter(status='active').count(),
        }

        serializer = RTODashboardSerializer(data=stats)
        serializer.is_valid()
        return Response(serializer.data)


class PendingVerificationsView(generics.ListAPIView):
    """
    GET /api/v1/rto/pending/
    All items (vehicles, drivers) awaiting RTO verification.
    Filter by ?type=vehicle or ?type=driver
    """
    serializer_class   = VerificationRecordSerializer
    permission_classes = [IsRTOOnly]
    filterset_fields   = ['item_type', 'decision']

    def get_queryset(self):
        return (VerificationRecord.objects
                .filter(decision='pending')
                .select_related('vehicle', 'driver', 'rto_officer')
                .order_by('created_at'))

    @extend_schema(tags=['rto'], summary='List all pending verifications')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VerifyVehicleView(APIView):
    """
    POST /api/v1/rto/verify/vehicle/<vehicle_id>/
    Approve or reject a vehicle.
    Body: { "action": "approve" | "reject", "reason": "..." }
    """
    permission_classes = [IsRTOOnly]

    @extend_schema(
        tags=['rto'],
        summary='Approve or reject a vehicle',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['approve', 'reject', 'flag']},
                    'reason': {'type': 'string'},
                    'notes':  {'type': 'string'},
                },
                'required': ['action']
            }
        }
    )
    def post(self, request, vehicle_id):
        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({'error': 'Vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action', '').lower()
        reason = request.data.get('reason', '')
        notes  = request.data.get('notes', '')

        if action not in ['approve', 'reject', 'flag']:
            return Response({'error': 'action must be approve, reject, or flag.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Update vehicle status
        if action == 'approve':
            vehicle.status          = Vehicle.Status.ACTIVE
            vehicle.rto_verified    = True
            vehicle.rto_verified_at = timezone.now()
            vehicle.rto_verified_by = request.user
            vehicle.rejection_reason = ''
            new_status = 'active'
        elif action == 'reject':
            vehicle.status           = Vehicle.Status.REJECTED
            vehicle.rto_verified     = False
            vehicle.rejection_reason = reason
            new_status = 'rejected'
        else:  # flag
            vehicle.status = Vehicle.Status.FLAGGED
            new_status = 'flagged'

        vehicle.save()

        # Create verification record
        record = VerificationRecord.objects.create(
            item_type   = 'vehicle',
            vehicle     = vehicle,
            rto_officer = request.user,
            decision    = 'approved' if action == 'approve' else action + 'ed',
            reason      = reason,
            notes       = notes,
            decided_at  = timezone.now(),
        )

        # Audit log
        log_rto_action(
            request.user, f'vehicle_{action}',
            'vehicle', vehicle.id,
            f'{vehicle.reg_number} → {action}. {reason}',
            request.META.get('REMOTE_ADDR')
        )

        # Notify owner via SMS/push
        from apps.notifications.tasks import notify_vehicle_status_change
        notify_vehicle_status_change.delay(vehicle.id, new_status, reason)

        logger.info(f'RTO {request.user.name} {action}d vehicle {vehicle.reg_number}')

        return Response({
            'message':  f'Vehicle {vehicle.reg_number} has been {action}d.',
            'vehicle_id': vehicle.id,
            'status':   vehicle.status,
            'record_id': record.id,
        })


class VerifyDriverView(APIView):
    """
    POST /api/v1/rto/verify/driver/<driver_id>/
    Approve or reject a driver's license.
    """
    permission_classes = [IsRTOOnly]

    @extend_schema(tags=['rto'], summary='Approve or reject a driver license')
    def post(self, request, driver_id):
        try:
            driver = User.objects.get(pk=driver_id, role='driver')
            profile = driver.driver_profile
        except (User.DoesNotExist, Exception):
            return Response({'error': 'Driver not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action', '').lower()
        reason = request.data.get('reason', '')

        if action not in ['approve', 'reject']:
            return Response({'error': 'action must be approve or reject.'},
                            status=status.HTTP_400_BAD_REQUEST)

        profile.is_rto_verified = (action == 'approve')
        profile.save(update_fields=['is_rto_verified'])

        VerificationRecord.objects.create(
            item_type   = 'driver',
            driver      = driver,
            rto_officer = request.user,
            decision    = 'approved' if action == 'approve' else 'rejected',
            reason      = reason,
            decided_at  = timezone.now(),
        )

        log_rto_action(
            request.user, f'driver_{action}',
            'driver', driver.id,
            f'{driver.name} ({profile.license_number}) → {action}. {reason}',
            request.META.get('REMOTE_ADDR')
        )

        # SMS notify driver
        from apps.notifications.tasks import send_sms_task
        msg = (f'GramYatra: Your driver license has been {"APPROVED" if action=="approve" else "REJECTED"} '
               f'by RTO. {"You can now operate." if action=="approve" else f"Reason: {reason}"} -GY')
        send_sms_task.delay(driver.phone, msg, template='driver_verify')

        return Response({
            'message': f'Driver {driver.name} license {action}d.',
            'driver_id': driver.id,
            'is_rto_verified': profile.is_rto_verified,
        })


class ComplianceFlagListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/rto/flags/     — List compliance flags
    POST /api/v1/rto/flags/     — Create a new flag
    """
    serializer_class   = ComplianceFlagSerializer
    permission_classes = [IsRTOOnly]
    filterset_fields   = ['flag_type', 'status']

    def get_queryset(self):
        return ComplianceFlag.objects.select_related('vehicle', 'flagged_by').all()

    def perform_create(self, serializer):
        flag = serializer.save(flagged_by=self.request.user)
        log_rto_action(
            self.request.user, 'flag_created',
            'compliance_flag', flag.id,
            f'{flag.flag_type}: {flag.description[:100]}'
        )

    @extend_schema(tags=['rto'], summary='List / create compliance flags')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ResolveFlagView(APIView):
    """POST /api/v1/rto/flags/<id>/resolve/"""
    permission_classes = [IsRTOOnly]

    @extend_schema(tags=['rto'], summary='Resolve a compliance flag')
    def post(self, request, flag_id):
        try:
            flag = ComplianceFlag.objects.get(pk=flag_id)
        except ComplianceFlag.DoesNotExist:
            return Response({'error': 'Flag not found.'}, status=status.HTTP_404_NOT_FOUND)

        escalate = request.data.get('escalate', False)
        flag.status      = 'escalated' if escalate else 'resolved'
        flag.resolved_at = timezone.now()
        flag.save()

        log_rto_action(
            request.user,
            'flag_escalated' if escalate else 'flag_resolved',
            'compliance_flag', flag.id
        )
        return Response({'message': f'Flag {"escalated to police" if escalate else "resolved"}.',
                         'flag_id': flag.id, 'status': flag.status})


class AllVehiclesLiveView(APIView):
    """
    GET /api/v1/rto/live-map/
    All vehicles with their latest locations — for RTO live map.
    """
    permission_classes = [IsRTOOnly]

    @extend_schema(tags=['rto'], summary='Live map of all vehicles (RTO)')
    def get(self, request):
        from apps.tracking.services import get_vehicle_location_cached
        vehicles = Vehicle.objects.select_related('route', 'driver').all()

        result = []
        for v in vehicles:
            loc = get_vehicle_location_cached(v.id)
            result.append({
                'id':         v.id,
                'bus_code':   v.bus_code,
                'reg_number': v.reg_number,
                'status':     v.status,
                'rto_verified': v.rto_verified,
                'route':      v.route.name if v.route else None,
                'driver':     v.driver.name if v.driver else None,
                'location':   loc,
            })

        return Response({'count': len(result), 'vehicles': result})


class AuditLogView(generics.ListAPIView):
    """GET /api/v1/rto/audit-log/"""
    serializer_class   = RTOAuditLogSerializer
    permission_classes = [IsRTOOnly]
    queryset           = RTOAuditLog.objects.select_related('officer').all()
    filterset_fields   = ['action', 'target_type']
    search_fields      = ['action', 'detail']

    @extend_schema(tags=['rto'], summary='RTO audit log (immutable)')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RTOSendDataView(APIView):
    """
    POST /api/v1/rto/export/
    Owner submits all vehicle data to RTO for batch verification.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['rto'], summary='Owner submits fleet data to RTO')
    def post(self, request):
        if not (request.user.is_owner or request.user.is_rto):
            return Response({'error': 'Owner or RTO access required.'}, status=status.HTTP_403_FORBIDDEN)

        vehicles = Vehicle.objects.filter(owner=request.user, status='pending')
        if not vehicles.exists():
            return Response({'message': 'No pending vehicles to submit.'})

        # Create verification records for each pending vehicle
        records_created = 0
        for vehicle in vehicles:
            _, created = VerificationRecord.objects.get_or_create(
                vehicle=vehicle,
                item_type='vehicle',
                decision='pending',
                defaults={'notes': f'Submitted by owner on {timezone.now().date()}'}
            )
            if created:
                records_created += 1

        log_rto_action(
            request.user, 'owner_data_submitted',
            'owner', request.user.id,
            f'{records_created} vehicle(s) submitted for verification'
        )

        return Response({
            'message': f'{records_created} vehicle(s) submitted to RTO for verification.',
            'submitted_count': records_created,
        })
