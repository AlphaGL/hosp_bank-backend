from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = user.role
        # Return notifications meant for this user's role or all
        return Notification.objects.filter(
            target_role__in=[role, 'all']
        ).order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='unread')
    def unread(self, request):
        qs = self.get_queryset().filter(is_read=False)
        return Response({
            'count': qs.count(),
            'notifications': NotificationSerializer(qs[:20], many=True).data,
        })

    @action(detail=True, methods=['patch'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response({'message': 'Marked as read.'})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'message': 'All notifications marked as read.'})
