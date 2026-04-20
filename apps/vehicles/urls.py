from django.urls import path
from .views import (
    NearbyVehiclesView, VehicleListCreateView, VehicleDetailView,
    VehicleDocumentUploadView, AssignDriverView, VehicleSearchView
)

urlpatterns = [
    path('',                            VehicleListCreateView.as_view(),   name='vehicle-list-create'),
    path('nearby/',                     NearbyVehiclesView.as_view(),      name='vehicle-nearby'),
    path('search/',                     VehicleSearchView.as_view(),       name='vehicle-search'),
    path('<int:pk>/',                   VehicleDetailView.as_view(),       name='vehicle-detail'),
    path('<int:pk>/documents/',         VehicleDocumentUploadView.as_view(), name='vehicle-docs'),
    path('<int:pk>/assign-driver/',     AssignDriverView.as_view(),        name='vehicle-assign-driver'),
]
