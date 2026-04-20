from django.contrib import admin
from apps.routes.models import Route, Stop, Schedule


class StopInline(admin.TabularInline):
    model  = Stop
    extra  = 1
    fields = ['order', 'name', 'lat', 'lng', 'distance_from_start_km']


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['name', 'from_location', 'to_location', 'distance_km',
                    'fare_min', 'fare_max', 'is_active']
    list_filter  = ['is_active']
    search_fields = ['name', 'from_location', 'to_location']
    list_editable = ['is_active']
    inlines = [StopInline]


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display  = ['vehicle', 'route', 'departure', 'arrival', 'days', 'is_active']
    list_filter   = ['is_active', 'days']
    raw_id_fields = ['vehicle', 'route']
