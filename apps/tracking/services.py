"""
GramYatra — Cell Tower Triangulation Service

Algorithm:
  1. Receive RSSI readings from ≥3 towers
  2. Convert RSSI → estimated distance using log-distance path loss model
  3. Apply weighted centroid (weight ∝ 1/distance²) to get lat/lng
  4. Estimate accuracy from spread of towers

Path-loss model (rural environment):
  d = 10 ^ ((RSSI_offset - RSSI) / (10 × n))
  where n = path_loss_exponent (3.5 for rural)
"""

import math
import logging
from django.conf import settings
from django.core.cache import cache
from .models import CellTower

logger = logging.getLogger('apps.tracking')

# ── Configuration ──────────────────────────────────────────
CFG = settings.CELL_TRIANGULATION
PATH_LOSS_EXP    = CFG.get('PATH_LOSS_EXPONENT', 3.5)
RSSI_OFFSET      = CFG.get('RSSI_OFFSET_DBM', -40)
DEFAULT_ACCURACY = CFG.get('DEFAULT_ACCURACY_M', 1200)
CACHE_TTL        = CFG.get('CACHE_LOCATION_SECONDS', 30)


def rssi_to_distance_m(rssi_dbm: int) -> float:
    """
    Convert RSSI (dBm) to estimated distance in metres.
    Formula: d = 10 ^ ((RSSI_offset - RSSI) / (10 * n))
    Returns distance in metres.
    """
    if rssi_dbm >= RSSI_OFFSET:
        return 1.0  # Very close to tower
    exponent = (RSSI_OFFSET - rssi_dbm) / (10.0 * PATH_LOSS_EXP)
    distance_km = 10 ** exponent
    return distance_km * 1000  # Convert to metres


def triangulate(tower_readings: list) -> dict:
    """
    Triangulate position from a list of tower readings.

    Args:
        tower_readings: list of dicts:
            [
              {'tower_code': 'TOWER-A1042', 'rssi': -82},
              {'tower_code': 'TOWER-B2087', 'rssi': -94},
              {'tower_code': 'TOWER-C3014', 'rssi': -101},
              ...
            ]

    Returns:
        {
          'lat': float,
          'lng': float,
          'accuracy_m': int,
          'towers_used': int,
          'method': 'triangulation' | 'centroid' | 'single_tower',
        }
    """
    if not tower_readings or len(tower_readings) < 1:
        raise ValueError('At least 1 tower reading required.')

    # Fetch tower objects from DB
    codes = [r['tower_code'] for r in tower_readings]
    towers_db = {t.tower_code: t for t in CellTower.objects.filter(
        tower_code__in=codes, is_active=True
    )}

    valid = []
    for reading in tower_readings:
        code = reading.get('tower_code')
        rssi = reading.get('rssi', -100)
        tower = towers_db.get(code)
        if tower:
            dist_m  = rssi_to_distance_m(rssi)
            weight  = 1.0 / max(dist_m ** 2, 0.0001)
            valid.append({
                'tower':  tower,
                'rssi':   rssi,
                'dist_m': dist_m,
                'weight': weight,
            })

    if not valid:
        raise ValueError('No matching active towers found in database.')

    # ── Weighted centroid ──────────────────────────────────
    total_weight = sum(v['weight'] for v in valid)
    lat_weighted = sum(float(v['tower'].lat) * v['weight'] for v in valid)
    lng_weighted = sum(float(v['tower'].lng) * v['weight'] for v in valid)

    est_lat = lat_weighted / total_weight
    est_lng = lng_weighted / total_weight

    # ── Accuracy estimation ────────────────────────────────
    # Based on spread of towers and weakest signal distance
    if len(valid) >= 3:
        max_dist = max(v['dist_m'] for v in valid)
        accuracy  = int(min(max_dist * 0.4, DEFAULT_ACCURACY))
        method    = 'triangulation'
    elif len(valid) == 2:
        accuracy  = int(DEFAULT_ACCURACY * 1.5)
        method    = 'bilateration'
    else:
        accuracy  = DEFAULT_ACCURACY * 2
        method    = 'single_tower'

    logger.debug(
        f'Triangulated: ({est_lat:.6f}, {est_lng:.6f}) '
        f'±{accuracy}m using {len(valid)} towers [{method}]'
    )

    return {
        'lat':         round(est_lat, 7),
        'lng':         round(est_lng, 7),
        'accuracy_m':  accuracy,
        'towers_used': len(valid),
        'method':      method,
        'tower_details': [
            {
                'code':    v['tower'].tower_code,
                'rssi':    v['rssi'],
                'dist_m':  round(v['dist_m']),
                'operator': v['tower'].operator,
            }
            for v in valid
        ]
    }


def get_vehicle_location_cached(vehicle_id: int) -> dict | None:
    """
    Get latest triangulated position of a vehicle from cache,
    falling back to database if cache miss.
    """
    cache_key = f'vehicle_location:{vehicle_id}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    from .models import VehicleTracking
    latest = (VehicleTracking.objects
              .filter(vehicle_id=vehicle_id)
              .order_by('-timestamp')
              .first())
    if not latest:
        return None

    data = {
        'lat':        float(latest.lat),
        'lng':        float(latest.lng),
        'accuracy_m': latest.accuracy_m,
        'speed_kmh':  float(latest.speed_kmh),
        'bearing':    float(latest.bearing_deg),
        'timestamp':  latest.timestamp.isoformat(),
        'gps_used':   latest.gps_used,
    }
    cache.set(cache_key, data, timeout=CACHE_TTL)
    return data


def calculate_eta_minutes(vehicle_lat: float, vehicle_lng: float,
                           stop_lat: float, stop_lng: float,
                           speed_kmh: float = 30) -> int:
    """Estimate minutes until vehicle reaches a stop."""
    R = 6371
    d_lat = math.radians(stop_lat - vehicle_lat)
    d_lng = math.radians(stop_lng - vehicle_lng)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(vehicle_lat)) *
         math.cos(math.radians(stop_lat)) *
         math.sin(d_lng / 2) ** 2)
    dist_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    effective_speed = max(speed_kmh, 5)
    return max(1, int((dist_km / effective_speed) * 60))
