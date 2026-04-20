from django.urls import path
from apps.users.views.user_views import UserListView, UserDetailView, DriverDutyToggleView

urlpatterns = [
    path('',              UserListView.as_view(),       name='user-list'),
    path('<int:pk>/',     UserDetailView.as_view(),     name='user-detail'),
    path('driver/duty/',  DriverDutyToggleView.as_view(), name='driver-duty-toggle'),
]
