"""
GramYatra — User Management Views
"""

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from apps.users.models import User, DriverProfile
from apps.users.serializers import UserProfileSerializer, UserListSerializer
from apps.users.permissions import IsRTOOnly, IsDriver, IsDriverOrAbove


class UserListView(generics.ListAPIView):
    """GET /api/v1/users/ — RTO only: list all users."""
    serializer_class   = UserListSerializer
    permission_classes = [IsRTOOnly]
    filterset_fields   = ['role', 'is_active', 'is_verified']
    search_fields      = ['name', 'phone']
    ordering_fields    = ['date_joined', 'name']
    queryset           = User.objects.all()

    @extend_schema(tags=['users'], summary='List all users (RTO only)')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PATCH/DELETE /api/v1/users/<id>/"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    queryset           = User.objects.all()

    def get_permissions(self):
        if self.request.method in ['DELETE']:
            return [IsRTOOnly()]
        return [IsAuthenticated()]

    def get_object(self):
        obj = super().get_object()
        # Users can only see their own profile unless RTO
        if not self.request.user.is_rto and obj.id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only view your own profile.')
        return obj

    @extend_schema(tags=['users'], summary='Get user profile')
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DriverDutyToggleView(APIView):
    """
    POST /api/v1/users/driver/duty/
    Toggle driver on-duty / off-duty status.
    """
    permission_classes = [IsDriverOrAbove]

    @extend_schema(
        tags=['users'],
        summary='Toggle driver duty status',
        request={'application/json': {'type': 'object', 'properties': {'is_on_duty': {'type': 'boolean'}}}},
    )
    def post(self, request):
        try:
            profile = request.user.driver_profile
        except DriverProfile.DoesNotExist:
            return Response({'error': 'Driver profile not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_on_duty = request.data.get('is_on_duty', not profile.is_on_duty)
        profile.is_on_duty = is_on_duty
        profile.save(update_fields=['is_on_duty'])

        return Response({
            'is_on_duty': profile.is_on_duty,
            'message': 'You are now On Duty. Location tracking active.' if is_on_duty else 'You are now Off Duty.',
        })
