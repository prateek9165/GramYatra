"""
GramYatra — Tracking WebSocket Consumer

WebSocket endpoint: ws://host/ws/tracking/<vehicle_id>/

Consumers (travelers/RTO) connect to receive live location updates.
Drivers POST via REST; the server broadcasts to all subscribers.

Group naming: vehicle_<id>
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('apps.tracking')


class VehicleTrackingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that pushes live vehicle location to subscribers.

    Connect:  ws://<host>/ws/tracking/<vehicle_id>/
    Receive:  Driver sends location update (authenticated drivers only)
    Send:     Broadcast location to all subscribers of this vehicle
    """

    async def connect(self):
        self.vehicle_id = self.scope['url_route']['kwargs']['vehicle_id']
        self.group_name = f'vehicle_{self.vehicle_id}'
        self.user = self.scope.get('user', AnonymousUser())

        # Only authenticated users can subscribe
        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Join vehicle tracking group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current location immediately on connect
        location = await self.get_current_location()
        if location:
            await self.send(text_data=json.dumps({
                'type':    'location_update',
                'vehicle': self.vehicle_id,
                'data':    location,
            }))
        logger.info(f'WS connect: user {self.user.id} → vehicle {self.vehicle_id}')

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f'WS disconnect: user {self.user.id} ← vehicle {self.vehicle_id}')

    async def receive(self, text_data):
        """
        Only drivers assigned to this vehicle may send location updates via WS.
        Payload:
        {
            "type": "location_update",
            "towers": [
                {"tower_code": "TOWER-A1042", "rssi": -82},
                {"tower_code": "TOWER-B2087", "rssi": -94},
                {"tower_code": "TOWER-C3014", "rssi": -101}
            ],
            "gps_lat": 23.2599,   // optional
            "gps_lng": 77.4126,   // optional
            "speed_kmh": 45,
            "bearing": 270
        }
        """
        if not self.user.is_authenticated:
            return
        if not (self.user.is_driver or self.user.is_owner or self.user.is_rto):
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get('type') == 'location_update':
            saved = await self.save_location(data)
            if saved:
                # Broadcast to all subscribers of this vehicle
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type':    'broadcast_location',
                        'vehicle': self.vehicle_id,
                        'data':    saved,
                    }
                )

    async def broadcast_location(self, event):
        """Handle group broadcast — send to WebSocket client."""
        await self.send(text_data=json.dumps({
            'type':    'location_update',
            'vehicle': event['vehicle'],
            'data':    event['data'],
        }))

    # ── Database helpers ──────────────────────────────────

    @database_sync_to_async
    def get_current_location(self):
        from .services import get_vehicle_location_cached
        return get_vehicle_location_cached(self.vehicle_id)

    @database_sync_to_async
    def save_location(self, data):
        """Triangulate and persist location, return serialisable dict."""
        try:
            from apps.vehicles.models import Vehicle
            from .models import CellTower, VehicleTracking
            from .services import triangulate

            vehicle = Vehicle.objects.get(pk=self.vehicle_id, status='active')

            towers = data.get('towers', [])
            if len(towers) < 1:
                return None

            result = triangulate(towers)

            # Resolve tower FK objects
            tower_objs = {t['code']: CellTower.objects.get(tower_code=t['code'])
                          for t in result['tower_details']
                          if CellTower.objects.filter(tower_code=t['code']).exists()}

            tower_list = result['tower_details']

            tracking = VehicleTracking.objects.create(
                vehicle    = vehicle,
                lat        = result['lat'],
                lng        = result['lng'],
                accuracy_m = result['accuracy_m'],
                speed_kmh  = data.get('speed_kmh', 0),
                bearing_deg = data.get('bearing', 0),
                tower1     = tower_objs.get(tower_list[0]['code']) if len(tower_list) > 0 else None,
                tower1_rssi = tower_list[0]['rssi'] if len(tower_list) > 0 else -100,
                tower2     = tower_objs.get(tower_list[1]['code']) if len(tower_list) > 1 else None,
                tower2_rssi = tower_list[1]['rssi'] if len(tower_list) > 1 else -100,
                tower3     = tower_objs.get(tower_list[2]['code']) if len(tower_list) > 2 else None,
                tower3_rssi = tower_list[2]['rssi'] if len(tower_list) > 2 else -100,
                gps_lat    = data.get('gps_lat'),
                gps_lng    = data.get('gps_lng'),
                gps_used   = bool(data.get('gps_lat')),
            )

            # Update cache
            from django.core.cache import cache
            cache_data = {
                'lat':        result['lat'],
                'lng':        result['lng'],
                'accuracy_m': result['accuracy_m'],
                'speed_kmh':  float(data.get('speed_kmh', 0)),
                'bearing':    float(data.get('bearing', 0)),
                'timestamp':  tracking.timestamp.isoformat(),
                'gps_used':   tracking.gps_used,
            }
            cache.set(f'vehicle_location:{self.vehicle_id}', cache_data, timeout=30)
            return cache_data

        except Exception as e:
            logger.error(f'WS save_location error for vehicle {self.vehicle_id}: {e}')
            return None


class AllVehiclesTrackingConsumer(AsyncWebsocketConsumer):
    """
    ws://<host>/ws/tracking/all/
    RTO-only consumer that receives updates for ALL vehicles simultaneously.
    """

    async def connect(self):
        self.user = self.scope.get('user', AnonymousUser())
        if not self.user.is_authenticated or not self.user.is_rto:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add('all_vehicles', self.channel_name)
        await self.accept()
        logger.info(f'RTO {self.user.id} connected to all-vehicles tracking stream')

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('all_vehicles', self.channel_name)

    async def receive(self, text_data):
        pass  # RTO is read-only on this stream

    async def broadcast_location(self, event):
        await self.send(text_data=json.dumps(event))
