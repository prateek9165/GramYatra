"""
URL configuration for gramyatra project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='login-page'),
    path('consumer/', TemplateView.as_view(template_name='consumer.html'), name='consumer-page'),
    path('driver/', TemplateView.as_view(template_name='driver.html'), name='driver-page'),
    path('owner/', TemplateView.as_view(template_name='owner.html'), name='owner-page'),
    path('rto-portal/', TemplateView.as_view(template_name='rto.html'), name='rto-page'),
    path('admin/', admin.site.urls),
    path('users/', include('apps.users.urls')),
    path('vehicles/', include('apps.vehicles.urls')),
    path('tracking/', include('apps.tracking.urls')),
    path('routes/', include('apps.routes.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('rto/', include('apps.rto.urls')),
]
