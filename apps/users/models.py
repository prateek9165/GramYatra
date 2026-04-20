"""
GramYatra — Users App Models
Custom User model with RBAC roles
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone, name, role='consumer', password=None, **extra_fields):
        if not phone:
            raise ValueError('Phone number is required')
        user = self.model(phone=phone, name=name, role=role, **extra_fields)
        user.set_password(password or self.make_random_password())
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone, name, role='rto', password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central user model for all 4 roles.
    Access control is enforced via role field + RBAC permission classes.
    """

    class Role(models.TextChoices):
        CONSUMER = 'consumer', 'Consumer (Traveler)'
        DRIVER   = 'driver',   'Driver'
        OWNER    = 'owner',    'Vehicle Owner'
        RTO      = 'rto',      'RTO Officer'

    # Core fields
    phone       = models.CharField(max_length=15, unique=True, db_index=True)
    name        = models.CharField(max_length=150)
    role        = models.CharField(max_length=10, choices=Role.choices, default=Role.CONSUMER, db_index=True)

    # Status
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    # Metadata
    preferred_language = models.CharField(
        max_length=5,
        choices=[('en', 'English'), ('hi', 'Hindi'), ('mr', 'Marathi')],
        default='en'
    )
    sms_alerts_enabled   = models.BooleanField(default=True)
    push_alerts_enabled  = models.BooleanField(default=True)
    offline_cache_enabled = models.BooleanField(default=True)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login  = models.DateTimeField(null=True, blank=True)

    # RTO-specific: passkey hash is validated at login time
    rto_passkey_hash = models.CharField(max_length=128, blank=True)

    objects = UserManager()

    USERNAME_FIELD  = 'phone'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table   = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.name} ({self.phone}) — {self.role}'

    # ── Role helpers ──────────────────────────────
    @property
    def is_consumer(self): return self.role == self.Role.CONSUMER
    @property
    def is_driver(self):   return self.role == self.Role.DRIVER
    @property
    def is_owner(self):    return self.role == self.Role.OWNER
    @property
    def is_rto(self):      return self.role == self.Role.RTO

    def can_access_consumer_interface(self):
        return self.role in [self.Role.CONSUMER, self.Role.DRIVER, self.Role.OWNER, self.Role.RTO]

    def can_access_driver_interface(self):
        return self.role in [self.Role.DRIVER, self.Role.OWNER, self.Role.RTO]

    def can_access_owner_interface(self):
        return self.role in [self.Role.OWNER, self.Role.RTO]

    def can_access_rto_interface(self):
        return self.role == self.Role.RTO


class DriverProfile(models.Model):
    """Extended profile for drivers."""
    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    license_number    = models.CharField(max_length=30, unique=True)
    license_document  = models.FileField(upload_to='uploads/licenses/', blank=True)
    license_expiry    = models.DateField(null=True, blank=True)
    is_rto_verified   = models.BooleanField(default=False)
    total_trips       = models.PositiveIntegerField(default=0)
    rating            = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    is_on_duty        = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'driver_profiles'

    def __str__(self):
        return f'Driver: {self.user.name} | License: {self.license_number}'


class OwnerProfile(models.Model):
    """Extended profile for vehicle owners/operators."""
    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='owner_profile')
    operator_id     = models.CharField(max_length=30, unique=True, blank=True)
    company_name    = models.CharField(max_length=150, blank=True)
    is_rto_verified = models.BooleanField(default=False)
    rto_verified_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'owner_profiles'

    def save(self, *args, **kwargs):
        if not self.operator_id:
            import uuid
            self.operator_id = f'OWN-MP-{timezone.now().year}-{str(uuid.uuid4())[:4].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Owner: {self.user.name} | ID: {self.operator_id}'
