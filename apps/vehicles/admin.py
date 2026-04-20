from django.contrib import admin
from apps.vehicles.models import Vehicle, VehicleDocument


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display   = ['bus_code', 'reg_number', 'model_name', 'status',
                      'rto_verified', 'owner', 'driver', 'route']
    list_filter    = ['status', 'rto_verified', 'vehicle_type']
    search_fields  = ['reg_number', 'bus_code', 'model_name']
    raw_id_fields  = ['owner', 'driver', 'route', 'rto_verified_by']
    readonly_fields = ['rto_verified_at', 'created_at', 'updated_at']
    list_editable  = ['status', 'rto_verified']


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(admin.ModelAdmin):
    list_display  = ['vehicle', 'doc_type', 'expiry_date', 'is_verified', 'is_expired']
    list_filter   = ['doc_type', 'is_verified']
    search_fields = ['vehicle__reg_number']
