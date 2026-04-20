"""
GramYatra — RTO Serializers
"""

from rest_framework import serializers
from .models import VerificationRecord, ComplianceFlag, RTOAuditLog
from apps.vehicles.serializers import VehicleSerializer
from apps.users.serializers import UserListSerializer


class VerificationRecordSerializer(serializers.ModelSerializer):
    vehicle_info = VehicleSerializer(source='vehicle', read_only=True)
    driver_info  = UserListSerializer(source='driver',  read_only=True)
    officer_name = serializers.CharField(source='rto_officer.name', read_only=True)

    class Meta:
        model  = VerificationRecord
        fields = [
            'id', 'item_type', 'vehicle', 'vehicle_info',
            'driver', 'driver_info', 'rto_officer', 'officer_name',
            'decision', 'notes', 'reason', 'decided_at', 'created_at',
        ]
        read_only_fields = ['rto_officer', 'decided_at', 'created_at']


class ComplianceFlagSerializer(serializers.ModelSerializer):
    flagged_by_name = serializers.CharField(source='flagged_by.name', read_only=True)

    class Meta:
        model  = ComplianceFlag
        fields = [
            'id', 'vehicle', 'reg_number', 'flag_type', 'description',
            'lat', 'lng', 'flagged_by', 'flagged_by_name',
            'status', 'created_at', 'resolved_at',
        ]
        read_only_fields = ['flagged_by', 'created_at']


class RTOAuditLogSerializer(serializers.ModelSerializer):
    officer_name = serializers.CharField(source='officer.name', read_only=True)

    class Meta:
        model  = RTOAuditLog
        fields = ['id', 'officer', 'officer_name', 'action',
                  'target_type', 'target_id', 'detail', 'ip_address', 'timestamp']


class RTODashboardSerializer(serializers.Serializer):
    """Read-only dashboard stats."""
    total_vehicles       = serializers.IntegerField()
    pending_vehicles     = serializers.IntegerField()
    approved_vehicles    = serializers.IntegerField()
    rejected_vehicles    = serializers.IntegerField()
    flagged_vehicles     = serializers.IntegerField()
    total_drivers        = serializers.IntegerField()
    pending_drivers      = serializers.IntegerField()
    total_routes         = serializers.IntegerField()
    active_buses_now     = serializers.IntegerField()
    open_compliance_flags = serializers.IntegerField()
    sms_today            = serializers.IntegerField()
    emergencies_active   = serializers.IntegerField()
