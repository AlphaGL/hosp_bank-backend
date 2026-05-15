from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import ListView

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    """GET /notifications/ — list all notifications for the current user's role."""
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        role = self.request.user.role
        return Notification.objects.filter(
            target_role__in=[role, 'all']
        ).order_by('-created_at')


class NotificationDetailView(LoginRequiredMixin, View):
    """GET /notifications/<pk>/ — detail view for a single notification."""
    template_name = 'notifications/notification_detail.html'

    def get(self, request, pk):
        role = request.user.role
        notification = get_object_or_404(
            Notification,
            pk=pk,
            target_role__in=[role, 'all'],
        )
        return render(request, self.template_name, {'notification': notification})


class UnreadNotificationsView(LoginRequiredMixin, View):
    """GET /notifications/unread/ — unread notifications for the current user's role."""
    template_name = 'notifications/unread_list.html'

    def get(self, request):
        role = request.user.role
        qs = Notification.objects.filter(
            target_role__in=[role, 'all'],
            is_read=False,
        ).order_by('-created_at')
        return render(request, self.template_name, {
            'notifications': qs[:20],
            'count': qs.count(),
        })


class MarkNotificationReadView(LoginRequiredMixin, View):
    """POST /notifications/<pk>/mark-read/ — mark a single notification as read."""

    def post(self, request, pk):
        role = request.user.role
        notification = get_object_or_404(
            Notification,
            pk=pk,
            target_role__in=[role, 'all'],
        )
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return JsonResponse({'message': 'Marked as read.'})


class MarkAllReadView(LoginRequiredMixin, View):
    """POST /notifications/mark-all-read/ — mark every visible notification as read."""

    def post(self, request):
        role = request.user.role
        Notification.objects.filter(
            target_role__in=[role, 'all'],
            is_read=False,
        ).update(is_read=True)
        return JsonResponse({'message': 'All notifications marked as read.'})