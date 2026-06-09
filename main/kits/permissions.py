from rest_framework import permissions


def is_staff_or_moderator(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_moderator)


class IsStaffOrModerator(permissions.BasePermission):
    message = 'You do not have permission to access this resource.'

    def has_permission(self, request, view):
        return is_staff_or_moderator(request.user)
