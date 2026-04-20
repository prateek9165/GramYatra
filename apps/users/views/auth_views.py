"""
GramYatra — Auth Views
Register, Login, Logout, Token Refresh
"""

import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import extend_schema, OpenApiExample

from ..serializers import (
    ConsumerRegisterSerializer, DriverRegisterSerializer,
    OwnerRegisterSerializer, RTORegisterSerializer,
    LoginSerializer, UserProfileSerializer
)
from ..models import User

logger = logging.getLogger('apps.users')


class RegisterView(APIView):
    """
    POST /api/v1/auth/register/
    Role-aware registration endpoint.
    Pass `role` in request body to determine which serializer is used.
    """
    permission_classes = [AllowAny]

    SERIALIZER_MAP = {
        'consumer': ConsumerRegisterSerializer,
        'driver':   DriverRegisterSerializer,
        'owner':    OwnerRegisterSerializer,
        'rto':      RTORegisterSerializer,
    }

    @extend_schema(
        tags=['auth'],
        summary='Register a new user',
        description='Register as Consumer, Driver, Owner, or RTO Officer.',
    )
    def post(self, request):
        role = request.data.get('role', 'consumer').lower()
        serializer_class = self.SERIALIZER_MAP.get(role)

        if not serializer_class:
            return Response(
                {'error': f'Invalid role. Choose from: {", ".join(self.SERIALIZER_MAP.keys())}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = LoginSerializer().get_tokens(user)
            logger.info(f'New user registered: {user.phone} as {user.role}')
            return Response({
                'message': 'Registration successful.',
                'user': UserProfileSerializer(user).data,
                'tokens': tokens,
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Returns JWT access + refresh tokens.
    """
    permission_classes = [AllowAny]

    @extend_schema(tags=['auth'], summary='Login and get JWT tokens')
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            tokens = serializer.get_tokens(user)
            logger.info(f'User logged in: {user.phone} ({user.role})')

            return Response({
                'message': 'Login successful.',
                'user': UserProfileSerializer(user).data,
                'tokens': tokens,
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['auth'], summary='Logout and blacklist refresh token')
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully.'})
        except TokenError:
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    """
    POST /api/v1/auth/token/refresh/
    """
    permission_classes = [AllowAny]

    @extend_schema(tags=['auth'], summary='Refresh access token')
    def post(self, request):
        try:
            refresh = RefreshToken(request.data.get('refresh'))
            return Response({'access': str(refresh.access_token)})
        except TokenError as e:
            return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class MeView(APIView):
    """
    GET /api/v1/auth/me/
    Returns current user's full profile.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['auth'], summary='Get current user profile')
    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)

    @extend_schema(tags=['auth'], summary='Update current user profile')
    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
