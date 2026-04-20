from django.contrib import admin
from apps.rto.models import VerificationRecord, ComplianceFlag, RTOAuditLog


@admin.register(VerificationRecord)
class VerificationRecordAdmin(admin.ModelAdmin):
    list_display  = ['item_type', 'vehicle', 'driver', 'rto_officer',
                     'decision', 'decided_at', 'created_at']
    list_filter   = ['item_type', 'decision']
    raw_id_fields = ['vehicle', 'driver', 'rto_officer']
    readonly_fields = ['created_at', 'decided_at']


@admin.register(ComplianceFlag)
class ComplianceFlagAdmin(admin.ModelAdmin):
    list_display  = ['flag_type', 'vehicle', 'reg_number', 'status',
                     'flagged_by', 'created_at']
    list_filter   = ['flag_type', 'status']
    list_editable = ['status']
    search_fields = ['reg_number', 'description']


@admin.register(RTOAuditLog)
class RTOAuditLogAdmin(admin.ModelAdmin):
    list_display   = ['officer', 'action', 'target_type', 'target_id',
                      'ip_address', 'timestamp']
    list_filter    = ['action', 'target_type']
    search_fields  = ['officer__name', 'action', 'detail']
    readonly_fields = ['officer', 'action', 'target_type', 'target_id',
                       'detail', 'ip_address', 'timestamp']
    date_hierarchy  = 'timestamp'

    def has_add_permission(self, request):
        return False  # Audit logs are immutable

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
