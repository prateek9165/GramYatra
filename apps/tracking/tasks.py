"""
GramYatra — Tracking Celery Tasks
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('apps.tracking')


@shared_task
def cleanup_old_tracking_points():
    """Delete tracking records older than 7 days to keep DB lean."""
    from .models import VehicleTracking
    cutoff = timezone.now() - timezone.timedelta(days=7)
    deleted, _ = VehicleTracking.objects.filter(timestamp__lt=cutoff).delete()
    logger.info(f'Cleaned up {deleted} old tracking records.')
    return {'deleted': deleted}
