from django.urls import path
from .views import (
    RTODashboardView, PendingVerificationsView,
    VerifyVehicleView, VerifyDriverView,
    ComplianceFlagListCreateView, ResolveFlagView,
    AllVehiclesLiveView, AuditLogView, RTOSendDataView,
)

urlpatterns = [
    path('dashboard/',                          RTODashboardView.as_view(),             name='rto-dashboard'),
    path('pending/',                            PendingVerificationsView.as_view(),     name='rto-pending'),
    path('verify/vehicle/<int:vehicle_id>/',    VerifyVehicleView.as_view(),            name='rto-verify-vehicle'),
    path('verify/driver/<int:driver_id>/',      VerifyDriverView.as_view(),             name='rto-verify-driver'),
    path('flags/',                              ComplianceFlagListCreateView.as_view(), name='rto-flags'),
    path('flags/<int:flag_id>/resolve/',        ResolveFlagView.as_view(),              name='rto-flag-resolve'),
    path('live-map/',                           AllVehiclesLiveView.as_view(),          name='rto-live-map'),
    path('audit-log/',                          AuditLogView.as_view(),                 name='rto-audit-log'),
    path('export/',                             RTOSendDataView.as_view(),              name='rto-export'),
]
