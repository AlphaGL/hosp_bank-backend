"""
Replaces DRF BasePermission classes with Django LoginRequiredMixin + UserPassesTestMixin combos.

Usage in views:
    class MyView(AdminRequiredMixin, View): ...
    class MyView(FinanceRequiredMixin, ListView): ...

Each mixin handles both authentication (redirects to login if not logged in)
and authorisation (returns 403 if the role test fails).
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Replaces IsAdmin. Only admin staff (or Django superusers) may access."""
    def test_func(self):
        return self.request.user.is_admin


class ReceptionistRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Replaces IsReceptionist / IsReceptionistOrAdmin."""
    def test_func(self):
        u = self.request.user
        return u.is_receptionist or u.is_admin


class FinanceRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Replaces IsFinance."""
    def test_func(self):
        u = self.request.user
        return u.is_finance or u.is_admin


class DoctorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Replaces IsDoctor."""
    def test_func(self):
        u = self.request.user
        return u.is_doctor or u.is_admin


class AdminOrReadOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Replaces IsAdminOrReadOnly.
    Allows GET/HEAD/OPTIONS for any authenticated user; everything else admin-only.
    """
    SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

    def test_func(self):
        if self.request.method in self.SAFE_METHODS:
            return self.request.user.is_authenticated
        return self.request.user.is_admin