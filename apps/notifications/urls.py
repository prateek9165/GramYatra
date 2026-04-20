from django.urls import path
from .views import (
    NotificationListView,
    MarkReadView,
    SetBusAlertView,
    EmergencyAlertCreateView,
    SMSLogView,
    SendTestSMSView,
)

urlpatterns = [
    path('',             NotificationListView.as_view(),    name='notification-list'),
    path('mark-read/',   MarkReadView.as_view(),            name='notification-mark-read'),
    path('set-alert/',   SetBusAlertView.as_view(),         name='bus-alert-set'),
    path('emergency/',   EmergencyAlertCreateView.as_view(),name='emergency-alert'),
    path('sms-log/',     SMSLogView.as_view(),              name='sms-log'),
    path('sms-test/',    SendTestSMSView.as_view(),         name='sms-test'),
]