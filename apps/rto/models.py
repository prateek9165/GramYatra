"""
GramYatra — RTO App Models
Verification records, compliance checks, audit logs
"""

from django.db import models
from django.conf import settings


class VerificationRecord(models.Model):
    """
    Tracks every RTO verification action on a vehicle or driver.
    """

    class ItemType(models.TextChoices):
        VEHICLE = 'vehicle', 'Vehicle'
        DRIVER  = 'driver',  'Driver'
        DOCUMENT = 'document', 'Document'

    class Decision(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        FLAGGED  = 'flagged',  'Flagged for Inspection'

    item_type   = models.CharField(max_length=10, choices=ItemType.choices, db_index=True)
    vehicle     = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.CASCADE,
        null=True, blank=True, related_name='verification_records'
    )
    driver      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='verification_records',
        limit_choices_to={'role': 'driver'}
    )
    rto_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rto_actions',
        limit_choices_to={'role': 'rto'}
    )
    decision    = models.CharField(max_length=10, choices=Decision.choices,
                                   default=Decision.PENDING, db_index=True)
    notes       = models.TextField(blank=True)
    reason      = models.TextField(blank=True, help_text='Reason for rejection/flagging')
    decided_at  = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'verification_records'
        ordering = ['-created_at']

    def __str__(self):
        subject = self.vehicle.reg_number if self.vehicle else (
            self.driver.name if self.driver else '?')
        return f'[{self.item_type}] {subject} → {self.decision}'


class ComplianceFlag(models.Model):
    """
    Non-compliant / illegal vehicles detected on routes.
    Can be raised by the system (unregistered detection) or manually by RTO.
    """

    class FlagType(models.TextChoices):
        UNREGISTERED  = 'unregistered',  'Unregistered Vehicle'
        EXPIRED_DOCS  = 'expired_docs',  'Expired Documents'
        INVALID_ROUTE = 'invalid_route', 'Operating on Unauthorized Route'
        OVERLOADING   = 'overloading',   'Passenger Overloading'
        OTHER         = 'other',         'Other Violation'

    class FlagStatus(models.TextChoices):
        OPEN     = 'open',     'Open'
        RESOLVED = 'resolved', 'Resolved'
        ESCALATED= 'escalated','Escalated to Police'

    vehicle     = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='compliance_flags'
    )
    reg_number  = models.CharField(max_length=20, blank=True,
                                   help_text='For unregistered vehicles not in DB')
    flag_type   = models.CharField(max_length=20, choices=FlagType.choices, db_index=True)
    description = models.TextField()
    lat         = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    lng         = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    flagged_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='flags_raised'
    )
    status      = models.CharField(max_length=10, choices=FlagStatus.choices,
                                   default=FlagStatus.OPEN, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'compliance_flags'
        ordering = ['-created_at']

    def __str__(self):
        subject = self.vehicle.reg_number if self.vehicle else self.reg_number
        return f'FLAG [{self.flag_type}] {subject} — {self.status}'


class RTOAuditLog(models.Model):
    """
    Immutable audit trail of every RTO officer action.
    """
    officer     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='audit_logs'
    )
    action      = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50, blank=True)
    target_id   = models.PositiveIntegerField(null=True, blank=True)
    detail      = models.TextField(blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rto_audit_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp}] {self.officer} → {self.action}'
