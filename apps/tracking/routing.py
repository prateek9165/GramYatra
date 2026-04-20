from django.urls import re_path
from .consumers import VehicleTrackingConsumer, AllVehiclesTrackingConsumer

websocket_urlpatterns = [
    re_path(r'^ws/tracking/all/$',                    AllVehiclesTrackingConsumer.as_asgi()),
    re_path(r'^ws/tracking/(?P<vehicle_id>\d+)/$',    VehicleTrackingConsumer.as_asgi()),
]
