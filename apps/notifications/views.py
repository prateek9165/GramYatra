"""
GramYatra — Notifications Views + URLs
"""

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from drf_spectacular.utils import extend_schema

from .models import Notification, BusAlertSubscription, EmergencyAlert, SMSLog
from apps.users.permissions import IsConsumerOrAbove, IsRTOOnly


# ── Serializers ───────────────────────────────────────────
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = ['id', 'notif_type', 'title', 'body', 'channel',
                  'is_read', 'vehicle', 'created_at']


class BusAlertSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BusAlertSubscription
        fields = ['id', 'vehicle', 'alert_km', 'is_active', 'created_at']


class EmergencyAlertSerializer(serializers.ModelSerializer):
    raised_by_name = serializers.CharField(source='raised_by.name', read_only=True)

    class Meta:
        model  = EmergencyAlert
        fields = ['id', 'alert_type', 'lat', 'lng', 'description',
                  'status', 'raised_by_name', 'vehicle', 'created_at']
        read_only_fields = ['status', 'raised_by_name']


class SMSLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SMSLog
        fields = ['id', 'to_number', 'message', 'template', 'status', 'sent_at']


# ── Views ─────────────────────────────────────────────────
class NotificationListView(generics.ListAPIView):
    """GET /api/v1/notifications/ — User's own notifications."""
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(tags=['notifications'], summary='List my notifications')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MarkReadView(APIView):
    """POST /api/v1/notifications/mark-read/ — Mark all as read."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['notifications'], summary='Mark all notifications as read')
    def post(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': f'{count} notifications marked as read.'})


class SetBusAlertView(APIView):
    """
    POST /api/v1/notifications/set-alert/
    Subscribe to arrival alerts for a bus.
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['notifications'], summary='Subscribe to bus arrival alert')
    def post(self, request):
        serializer = BusAlertSubscriptionSerializer(data=request.data)
        if serializer.is_valid():
            sub, created = BusAlertSubscription.objects.get_or_create(
                user=request.user,
                vehicle_id=request.data['vehicle'],
                defaults={'alert_km': request.data.get('alert_km', 2.0)}
            )
            if not created:
                sub.is_active = True
                sub.alert_km  = request.data.get('alert_km', sub.alert_km)
                sub.save()
            return Response({
                'message': f'Alert set. You will be notified when bus is within {sub.alert_km} km.',
                'subscription': BusAlertSubscriptionSerializer(sub).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmergencyAlertCreateView(APIView):
    """
    POST /api/v1/notifications/emergency/
    Trigger an emergency alert (driver or consumer).
    """
    permission_classes = [IsConsumerOrAbove]

    @extend_schema(tags=['notifications'], summary='Trigger emergency alert')
    def post(self, request):
        serializer = EmergencyAlertSerializer(data=request.data)
        if serializer.is_valid():
            alert = serializer.save(raised_by=request.user)

            # Fire async task to broadcast to RTO
            from .tasks import send_emergency_alert_task
            send_emergency_alert_task.delay(alert.id)

            return Response({
                'message': 'Emergency alert sent to RTO and authorities.',
                'alert_id': alert.id,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SMSLogView(generics.ListAPIView):
    """GET /api/v1/notifications/sms-log/ — RTO audit log of all SMS."""
    serializer_class   = SMSLogSerializer
    permission_classes = [IsRTOOnly]
    queryset           = SMSLog.objects.all()
    filterset_fields   = ['status', 'template']

    @extend_schema(tags=['notifications'], summary='SMS audit log (RTO only)')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SendTestSMSView(APIView):
    """POST /api/v1/notifications/sms-test/ — RTO sends a test SMS."""
    permission_classes = [IsRTOOnly]

    @extend_schema(tags=['notifications'], summary='Send test SMS (RTO only)')
    def post(self, request):
        to     = request.data.get('to')
        msg    = request.data.get('message', 'GramYatra Test SMS — System is working.')
        if not to:
            return Response({'error': 'to (phone number) is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from .tasks import send_sms_task
        send_sms_task.delay(to, msg, template='test')
        return Response({'message': f'Test SMS queued for {to}.'})


# ── URLs ──────────────────────────────────────────────────
from django.urls import path

urlpatterns = [
    path('',             NotificationListView.as_view(),    name='notification-list'),
    path('mark-read/',   MarkReadView.as_view(),            name='notification-mark-read'),
    path('set-alert/',   SetBusAlertView.as_view(),         name='bus-alert-set'),
    path('emergency/',   EmergencyAlertCreateView.as_view(),name='emergency-alert'),
    path('sms-log/',     SMSLogView.as_view(),              name='sms-log'),
    path('sms-test/',    SendTestSMSView.as_view(),         name='sms-test'),
]
