"""
GramYatra — Tracking App Models
CellTower registry + VehicleTracking (cell-tower triangulated positions)
"""

from django.db import models
from django.conf import settings


class CellTower(models.Model):
    """
    Registry of all cell towers used for triangulation.
    Populated from BSNL/Airtel/Jio cell-tower databases or OpenCelliD.
    """
    tower_code         = models.CharField(max_length=30, unique=True, db_index=True)
    operator           = models.CharField(max_length=50, default='BSNL')

    # Location of Sthe tower itself
    lat                = models.DecimalField(max_digits=10, decimal_places=7)
    lng                = models.DecimalField(max_digits=10, decimal_places=7)

    # Cell identity
    mcc                = models.PositiveSmallIntegerField(default=404, help_text='Mobile Country Code')
    mnc                = models.PositiveSmallIntegerField(default=1,   help_text='Mobile Network Code')
    lac                = models.PositiveIntegerField(help_text='Location Area Code')
    cell_id            = models.PositiveIntegerField(help_text='Cell ID')

    # Signal characteristics
    coverage_radius_m  = models.PositiveIntegerField(default=3000)
    signal_strength_dbm = models.IntegerField(default=-80)
    frequency_band     = models.CharField(max_length=10, default='900MHz')
    technology         = models.CharField(
        max_length=5,
        choices=[('2G','2G GSM'),('3G','3G UMTS'),('4G','4G LTE')],
        default='2G'
    )

    is_active          = models.BooleanField(default=True, db_index=True)
    last_seen          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cell_towers'
        unique_together = ['mcc', 'mnc', 'lac', 'cell_id']

    def __str__(self):
        return f'{self.tower_code} ({self.operator}) @ {self.lat},{self.lng}'


class VehicleTracking(models.Model):
    """
    Every location ping from a driver's device.
    Stores the raw tower signals + the triangulated result.
    Indexed on (vehicle, timestamp) for efficient time-range queries.
    """
    vehicle     = models.ForeignKey(
        'vehicles.Vehicle', on_delete=models.CASCADE,
        related_name='tracking_points', db_index=True
    )

    # Triangulated position
    lat         = models.DecimalField(max_digits=10, decimal_places=7)
    lng         = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_m  = models.PositiveIntegerField(default=1200)

    # Movement
    speed_kmh   = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    bearing_deg = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                      help_text='Direction 0–360°')

    # Raw cell tower signals used (min 3)
    tower1      = models.ForeignKey(CellTower, on_delete=models.SET_NULL,
                                    null=True, related_name='+')
    tower1_rssi = models.IntegerField(default=-80, help_text='Signal strength dBm')
    tower2      = models.ForeignKey(CellTower, on_delete=models.SET_NULL,
                                    null=True, related_name='+')
    tower2_rssi = models.IntegerField(default=-90)
    tower3      = models.ForeignKey(CellTower, on_delete=models.SET_NULL,
                                    null=True, related_name='+')
    tower3_rssi = models.IntegerField(default=-100)

    # GPS fallback (optional)
    gps_lat     = models.DecimalField(max_digits=10, decimal_places=7,
                                       null=True, blank=True)
    gps_lng     = models.DecimalField(max_digits=10, decimal_places=7,
                                       null=True, blank=True)
    gps_used    = models.BooleanField(default=False)

    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'vehicle_tracking'
        ordering = ['-timestamp']
        indexes  = [
            models.Index(fields=['vehicle', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.vehicle.bus_code} @ {self.lat},{self.lng} [{self.timestamp}]'
