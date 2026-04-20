"""
GramYatra — Notification Celery Tasks
Async SMS sending, arrival alert checker, emergency broadcast
"""

import logging
import requests
from django.conf import settings
from django.utils import timezone
from celery import shared_task

logger = logging.getLogger('apps.notifications')

# ── SMS Templates ─────────────────────────────────────────
SMS_TEMPLATES = {
    'arrival': 'GramYatra: Bus {bus_code} ({route}) arriving in {eta} min at your stop. -GY',
    'delay':   'GramYatra: Bus {bus_code} DELAYED by {delay} min. New ETA: {new_eta}. Sorry! -GY',
    'route_change': 'GramYatra: Bus {bus_code} route changed today. New stop: {stop}. -GY',
    'rto_approved': 'GramYatra: Vehicle {reg} has been APPROVED by RTO. You can now operate. -GY',
    'rto_rejected': 'GramYatra: Vehicle {reg} was REJECTED by RTO. Reason: {reason}. -GY',
    'emergency': 'GramYatra EMERGENCY: {type} reported near {location}. Authorities notified. -GY',
    'driver_approved': 'GramYatra: Your driver account for {owner} has been APPROVED. -GY',
}


def send_sms_fast2sms(to_number: str, message: str) -> dict:
    """Send SMS via Fast2SMS API."""
    url = 'https://www.fast2sms.com/dev/bulkV2'
    headers = {'authorization': settings.SMS_API_KEY}
    payload = {
        'route':   'q',
        'message': message[:160],
        'numbers': to_number.lstrip('+91').lstrip('0'),
        'language':'english',
        'sender_id': settings.SMS_SENDER_ID,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.json()
    except requests.RequestException as e:
        logger.error(f'Fast2SMS error: {e}')
        return {'return': False, 'message': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_sms_task(self, to_number: str, message: str, template: str = ''):
    """Async task: send SMS and log result."""
    from .models import SMSLog
    log = SMSLog.objects.create(
        to_number=to_number,
        message=message,
        template=template,
        status='pending'
    )
    try:
        if settings.SMS_PROVIDER == 'fast2sms' and settings.SMS_API_KEY:
            result = send_sms_fast2sms(to_number, message)
            success = result.get('return', False)
        else:
            # Development mode: just log, don't actually send
            logger.info(f'[DEV SMS] To: {to_number} | Msg: {message}')
            success = True
            result = {'return': True, 'message': 'dev_mode'}

        log.status   = 'sent' if success else 'failed'
        log.provider_response = str(result)
        log.save(update_fields=['status', 'provider_response'])

        if not success:
            raise self.retry(exc=Exception('SMS failed'))

        logger.info(f'SMS sent to {to_number}')
        return {'success': True, 'to': to_number}

    except Exception as exc:
        log.status = 'failed'
        log.save(update_fields=['status'])
        raise self.retry(exc=exc)


@shared_task
def check_bus_arrival_alerts():
    """
    Periodic task (runs every 60s via Celery Beat).
    Checks all active BusAlertSubscriptions and sends SMS/push if
    the subscribed bus is within alert_km of the user's last known location.
    """
    from .models import BusAlertSubscription, Notification
    from apps.tracking.services import get_vehicle_location_cached
    import math

    subs = BusAlertSubscription.objects.filter(
        is_active=True,
        vehicle__status='active'
    ).select_related('user', 'vehicle', 'vehicle__route')

    for sub in subs:
        loc = get_vehicle_location_cached(sub.vehicle_id)
        if not loc:
            continue

        # We'd need user's last known lat/lng. For now use a placeholder.
        # In production, store user location from their last API call.
        user_lat = getattr(sub.user, '_last_lat', None)
        user_lng = getattr(sub.user, '_last_lng', None)
        if not user_lat or not user_lng:
            continue

        R = 6371
        d_lat = math.radians(loc['lat'] - user_lat)
        d_lng = math.radians(loc['lng'] - user_lng)
        a = (math.sin(d_lat/2)**2 +
             math.cos(math.radians(user_lat)) *
             math.cos(math.radians(loc['lat'])) *
             math.sin(d_lng/2)**2)
        dist_km = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        if dist_km <= sub.alert_km:
            eta = int((dist_km / max(loc.get('speed_kmh', 30), 5)) * 60)
            msg = SMS_TEMPLATES['arrival'].format(
                bus_code=sub.vehicle.bus_code,
                route=sub.vehicle.route.name if sub.vehicle.route else 'your route',
                eta=eta,
            )

            # Create in-app notification
            Notification.objects.get_or_create(
                user=sub.user,
                vehicle=sub.vehicle,
                notif_type='arrival',
                is_read=False,
                defaults={'title': f'Bus {sub.vehicle.bus_code} arriving in {eta} min',
                          'body': msg}
            )

            # Send SMS if enabled
            if sub.user.sms_alerts_enabled:
                send_sms_task.delay(sub.user.phone, msg, template='arrival')

            logger.info(f'Arrival alert sent: {sub.user.name} ← {sub.vehicle.bus_code}')


@shared_task
def send_emergency_alert_task(emergency_id: int):
    """Broadcast emergency to all RTO officers and nearby users via SMS."""
    from .models import EmergencyAlert, Notification
    from apps.users.models import User

    try:
        alert = EmergencyAlert.objects.get(pk=emergency_id)
    except EmergencyAlert.DoesNotExist:
        return

    location_str = f'{alert.lat:.4f}°N, {alert.lng:.4f}°E' if alert.lat else 'Unknown'
    msg = SMS_TEMPLATES['emergency'].format(
        type=alert.get_alert_type_display(),
        location=location_str
    )

    # Notify all RTO officers
    rto_users = User.objects.filter(role='rto', is_active=True)
    for rto in rto_users:
        Notification.objects.create(
            user=rto,
            notif_type='emergency',
            title=f'🚨 EMERGENCY: {alert.get_alert_type_display()}',
            body=f'Reported by {alert.raised_by.name} at {location_str}',
            channel='both',
            vehicle=alert.vehicle,
        )
        send_sms_task.delay(rto.phone, msg, template='emergency')

    logger.warning(f'Emergency {emergency_id} broadcast to {rto_users.count()} RTO officers')


@shared_task
def notify_vehicle_status_change(vehicle_id: int, new_status: str, reason: str = ''):
    """Notify owner when RTO approves/rejects their vehicle."""
    from apps.vehicles.models import Vehicle
    from .models import Notification

    try:
        vehicle = Vehicle.objects.select_related('owner').get(pk=vehicle_id)
    except Vehicle.DoesNotExist:
        return

    template_key = 'rto_approved' if new_status == 'active' else 'rto_rejected'
    msg = SMS_TEMPLATES[template_key].format(
        reg=vehicle.reg_number,
        reason=reason or 'See RTO notice'
    )
    title = (f'Vehicle {vehicle.reg_number} Approved ✅'
             if new_status == 'active'
             else f'Vehicle {vehicle.reg_number} Rejected ❌')

    Notification.objects.create(
        user=vehicle.owner,
        notif_type='rto',
        title=title,
        body=msg,
        channel='both',
        vehicle=vehicle,
    )
    if vehicle.owner.sms_alerts_enabled:
        send_sms_task.delay(vehicle.owner.phone, msg, template=template_key)
    logger.info(f'Owner {vehicle.owner.name} notified: vehicle {vehicle.reg_number} → {new_status}')
