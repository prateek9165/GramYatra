from django.urls import path
from .views import (
    RouteListView, RouteDetailView, RouteSearchView,
    TodayScheduleView, ScheduleManageView, AIRouteQueryView
)

urlpatterns = [
    path('',             RouteListView.as_view(),     name='route-list'),
    path('search/',      RouteSearchView.as_view(),   name='route-search'),
    path('schedule/',    TodayScheduleView.as_view(), name='route-schedule'),
    path('schedules/',   ScheduleManageView.as_view(),name='schedule-manage'),
    path('ai/',          AIRouteQueryView.as_view(),  name='route-ai'),
    path('<int:pk>/',    RouteDetailView.as_view(),   name='route-detail'),
]
