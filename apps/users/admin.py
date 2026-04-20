"""
GramYatra — Django Admin Configuration
Registers all models with rich admin interfaces
"""

# ── apps/users/admin.py ──────────────────────────────────
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.users.models import User, DriverProfile, OwnerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display   = ['phone', 'name', 'role', 'is_active', 'is_verified', 'date_joined']
    list_filter    = ['role', 'is_active', 'is_verified', 'preferred_language']
    search_fields  = ['name', 'phone']
    ordering       = ['-date_joined']
    fieldsets = (
        (None,              {'fields': ('phone', 'name', 'role', 'password')}),
        ('Status',          {'fields': ('is_active', 'is_verified', 'is_staff', 'is_superuser')}),
        ('Preferences',     {'fields': ('preferred_language', 'sms_alerts_enabled',
                                        'push_alerts_enabled', 'offline_cache_enabled')}),
        ('Dates',           {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('phone', 'name', 'role', 'password1', 'password2')}),
    )
    readonly_fields = ['date_joined', 'last_login']


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'license_number', 'is_rto_verified', 'is_on_duty', 'total_trips', 'rating']
    list_filter   = ['is_rto_verified', 'is_on_duty']
    search_fields = ['user__name', 'user__phone', 'license_number']


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'operator_id', 'company_name', 'is_rto_verified']
    search_fields = ['user__name', 'operator_id', 'company_name']
