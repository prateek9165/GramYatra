"""
GramYatra — Vehicles App Models
Vehicle, VehicleDocument
"""

from django.db import models
from django.conf import settings


class Vehicle(models.Model):

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending RTO Verification'
        ACTIVE   = 'active',   'Active'
        INACTIVE = 'inactive', 'Inactive'
        REJECTED = 'rejected', 'Rejected by RTO'
        FLAGGED  = 'flagged',  'Flagged (Non-Compliant)'

    class VehicleType(models.TextChoices):
        BUS       = 'bus',       'Bus'
        MINIBUS   = 'minibus',   'Mini Bus'
        TEMPO     = 'tempo',     'Tempo Traveller'
        AUTO      = 'auto',      'Auto Rickshaw'

    # Ownership
    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='owned_vehicles', limit_choices_to={'role': 'owner'}
    )
    driver      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_vehicles',
        limit_choices_to={'role': 'driver'}
    )

    # Identity
    reg_number   = models.CharField(max_length=20, unique=True, db_index=True)
    bus_code     = models.CharField(max_length=10, unique=True, blank=True,
                                    help_text='Short code shown to users e.g. A01')
    model_name   = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=10, choices=VehicleType.choices,
                                    default=VehicleType.BUS)
    capacity     = models.PositiveSmallIntegerField(default=40)
    manufacture_year = models.PositiveSmallIntegerField(null=True, blank=True)

    # Status
    status           = models.CharField(max_length=10, choices=Status.choices,
                                        default=Status.PENDING, db_index=True)
    rto_verified     = models.BooleanField(default=False)
    rto_verified_at  = models.DateTimeField(null=True, blank=True)
    rto_verified_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rto_verified_vehicles',
        limit_choices_to={'role': 'rto'}
    )
    rejection_reason = models.TextField(blank=True)

    # Route
    route = models.ForeignKey(
        'routes.Route', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vehicles'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'vehicles'
        ordering  = ['-created_at']

    def __str__(self):
        return f'{self.bus_code} | {self.reg_number} ({self.model_name})'

    def save(self, *args, **kwargs):
        if not self.bus_code:
            # Auto-generate bus code from reg_number suffix
            suffix = ''.join(filter(str.isalnum, self.reg_number))[-4:]
            self.bus_code = suffix.upper()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class VehicleDocument(models.Model):

    class DocType(models.TextChoices):
        RC          = 'rc',          'Registration Certificate'
        INSURANCE   = 'insurance',   'Insurance'
        FITNESS     = 'fitness',     'Fitness Certificate'
        PERMIT      = 'permit',      'Route Permit'
        PUC         = 'puc',         'Pollution Certificate'
        TAX_TOKEN   = 'tax_token',   'Tax Token'

    vehicle    = models.ForeignKey(Vehicle, on_delete=models.CASCADE,
                                   related_name='documents')
    doc_type   = models.CharField(max_length=15, choices=DocType.choices)
    document   = models.FileField(upload_to='uploads/vehicle_docs/')
    expiry_date = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, limit_choices_to={'role': 'rto'}
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicle_documents'
        unique_together = ['vehicle', 'doc_type']

    def __str__(self):
        return f'{self.vehicle.reg_number} — {self.get_doc_type_display()}'

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()
