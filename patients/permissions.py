from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    """Only admin staff (or Django superusers) may access."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsReceptionist(BasePermission):
    """Receptionists and admins may access."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.is_receptionist or request.user.is_admin
            )
        )


class IsFinance(BasePermission):
    """Finance staff and admins may access."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.is_finance or request.user.is_admin
            )
        )


class IsDoctor(BasePermission):
    """Doctors/technicians and admins may access."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.is_doctor or request.user.is_admin
            )
        )


class IsReceptionistOrAdmin(BasePermission):
    """Receptionists or admins may access (alias kept for back-compat)."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and (
                request.user.is_receptionist or request.user.is_admin
            )
        )


class IsAdminOrReadOnly(BasePermission):
    """
    Allows full access to admins; everyone else gets read-only (GET/HEAD/OPTIONS).
    Useful for catalogue-style endpoints like DiagnosticService.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_admin