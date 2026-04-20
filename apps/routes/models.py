"""
GramYatra — Routes App Models
Route, Stop, Schedule
"""

from django.db import models
from django.conf import settings


class Route(models.Model):
    name          = models.CharField(max_length=150)
    from_location = models.CharField(max_length=100, db_index=True)
    to_location   = models.CharField(max_length=100, db_index=True)
    distance_km   = models.DecimalField(max_digits=7, decimal_places=2)
    fare_min      = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    fare_max      = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_active     = models.BooleanField(default=True, db_index=True)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'routes'

    def __str__(self):
        return f'{self.name}: {self.from_location} → {self.to_location}'


class Stop(models.Model):
    route      = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    name       = models.CharField(max_length=100)
    order      = models.PositiveSmallIntegerField(help_text='Stop sequence number')
    lat        = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    lng        = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    distance_from_start_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        db_table  = 'route_stops'
        ordering  = ['route', 'order']
        unique_together = ['route', 'order']

    def __str__(self):
        return f'{self.route.name} — Stop {self.order}: {self.name}'


class Schedule(models.Model):
    vehicle     = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE,
                                    related_name='schedules')
    route       = models.ForeignKey(Route, on_delete=models.CASCADE,
                                    related_name='schedules')
    departure   = models.TimeField(help_text='Scheduled departure time')
    arrival     = models.TimeField(help_text='Scheduled arrival time')
    days        = models.CharField(
        max_length=20,
        default='daily',
        help_text="'daily', 'weekdays', 'weekends', or comma-separated days: 'mon,wed,fri'"
    )
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'schedules'
        ordering = ['departure']

    def __str__(self):
        return f'{self.vehicle.bus_code} | {self.route.name} @ {self.departure}'

    def runs_today(self):
        from django.utils import timezone
        today = timezone.localdate().strftime('%a').lower()
        if self.days == 'daily':
            return True
        if self.days == 'weekdays':
            return today in ['mon','tue','wed','thu','fri']
        if self.days == 'weekends':
            return today in ['sat','sun']
        return today[:3] in [d.strip().lower()[:3] for d in self.days.split(',')]
