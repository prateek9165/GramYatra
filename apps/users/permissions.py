from rest_framework.permissions import BasePermission


class IsConsumerOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsDriverOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ['driver', 'owner', 'rto']
        )


class IsOwnerOrAbove(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ['owner', 'rto']
        )


class IsRTOOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'rto'
        )


class IsDriver(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'driver'
        )


class IsOwnerOfObject(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, 'is_rto', False):
            return True
        if hasattr(obj, 'owner') and obj.owner == request.user:
            return True
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        return False
