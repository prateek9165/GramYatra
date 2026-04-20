"""
GramYatra — Notifications App Models
"""

from django.db import models
from django.conf import settings


class Notification(models.Model):

    class NotifType(models.TextChoices):
        ARRIVAL  = 'arrival',  'Bus Arrival Alert'
        DELAY    = 'delay',    'Bus Delay Update'
        ROUTE    = 'route',    'Route Change'
        SYSTEM   = 'system',   'System Notification'
        EMERGENCY = 'emergency','Emergency Alert'
        RTO      = 'rto',      'RTO Compliance'

    class Channel(models.TextChoices):
        PUSH = 'push', 'Push (In-App)'
        SMS  = 'sms',  'SMS'
        BOTH = 'both', 'Push + SMS'

    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', db_index=True
    )
    notif_type  = models.CharField(max_length=15, choices=NotifType.choices, db_index=True)
    title       = models.CharField(max_length=200)
    body        = models.TextField()
    channel     = models.CharField(max_length=5, choices=Channel.choices, default=Channel.PUSH)
    is_read     = models.BooleanField(default=False, db_index=True)
    vehicle     = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notifications'
    )
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.notif_type}] → {self.user.name}: {self.title}'


class SMSLog(models.Model):
    """Log every SMS sent for audit and debugging."""

    class SMSStatus(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        SENT     = 'sent',     'Sent'
        FAILED   = 'failed',   'Failed'
        DELIVERED = 'delivered','Delivered'

    to_number  = models.CharField(max_length=15)
    message    = models.TextField()
    template   = models.CharField(max_length=50, blank=True)
    status     = models.CharField(max_length=10, choices=SMSStatus.choices,
                                  default=SMSStatus.PENDING)
    provider_response = models.TextField(blank=True)
    sent_at    = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sms_logs'
        ordering = ['-sent_at']

    def __str__(self):
        return f'SMS → {self.to_number} [{self.status}] @ {self.sent_at}'


class BusAlertSubscription(models.Model):
    """User subscribes to get notified when a specific bus is nearby."""
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='alert_subscriptions'
    )
    vehicle     = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.CASCADE,
        related_name='alert_subscriptions'
    )
    alert_km    = models.FloatField(default=2.0, help_text='Trigger alert within N km')
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bus_alert_subscriptions'
        unique_together = ['user', 'vehicle']

    def __str__(self):
        return f'{self.user.name} ← {self.vehicle.bus_code} within {self.alert_km}km'


class EmergencyAlert(models.Model):

    class AlertType(models.TextChoices):
        SOS       = 'sos',       'SOS'
        BREAKDOWN = 'breakdown', 'Vehicle Breakdown'
        ACCIDENT  = 'accident',  'Accident'
        SAFETY    = 'safety',    'Safety Issue'

    class AlertStatus(models.TextChoices):
        ACTIVE   = 'active',   'Active'
        RESOLVED = 'resolved', 'Resolved'

    raised_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='emergency_alerts'
    )
    vehicle     = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='emergencies'
    )
    alert_type  = models.CharField(max_length=15, choices=AlertType.choices)
    lat         = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    lng         = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=10, choices=AlertStatus.choices,
                                   default=AlertStatus.ACTIVE)
    created_at  = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'emergency_alerts'
        ordering = ['-created_at']

    def __str__(self):
        return f'EMERGENCY [{self.alert_type}] by {self.raised_by.name} @ {self.created_at}'
