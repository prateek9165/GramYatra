from django.urls import path
from .views import LocationUpdateView, LiveLocationView, LocationHistoryView, NearbyTowersView

urlpatterns = [
    path('update/',                          LocationUpdateView.as_view(),   name='tracking-update'),
    path('towers/',                          NearbyTowersView.as_view(),     name='tracking-towers'),
    path('<int:vehicle_id>/live/',           LiveLocationView.as_view(),     name='tracking-live'),
    path('<int:vehicle_id>/history/',        LocationHistoryView.as_view(),  name='tracking-history'),
]
