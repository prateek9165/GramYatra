"""
GramYatra — RTO Celery Tasks
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('apps.rto')


@shared_task
def check_expiring_documents():
    """
    Daily check: notify owners of vehicle documents expiring in 30 days.
    """
    from apps.vehicles.models import VehicleDocument
    from apps.notifications.tasks import send_sms_task

    expiry_threshold = timezone.now().date() + timezone.timedelta(days=30)
    expiring = VehicleDocument.objects.filter(
        expiry_date__lte=expiry_threshold,
        expiry_date__gte=timezone.now().date(),
        is_verified=True,
    ).select_related('vehicle__owner')

    notified = 0
    for doc in expiring:
        owner = doc.vehicle.owner
        days_left = (doc.expiry_date - timezone.now().date()).days
        msg = (f'GramYatra: Your {doc.get_doc_type_display()} for '
               f'{doc.vehicle.reg_number} expires in {days_left} days. '
               f'Renew to avoid service disruption. -GY')
        if owner.sms_alerts_enabled:
            send_sms_task.delay(owner.phone, msg, template='doc_expiry')
        notified += 1

    logger.info(f'Document expiry check: {notified} notifications sent.')
    return {'notified': notified}
