from django.urls import path
from apps.users.views.auth_views import RegisterView, LoginView, LogoutView, TokenRefreshView, MeView

urlpatterns = [
    path('register/',      RegisterView.as_view(),      name='auth-register'),
    path('login/',         LoginView.as_view(),          name='auth-login'),
    path('logout/',        LogoutView.as_view(),         name='auth-logout'),
    path('token/refresh/', TokenRefreshView.as_view(),   name='token-refresh'),
    path('me/',            MeView.as_view(),             name='auth-me'),
]
