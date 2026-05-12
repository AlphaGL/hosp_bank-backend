from .models import Notification

EVENT_TARGET_MAP = {
    'payment_confirmed': ['receptionist', 'admin'],
    'patient_queued': ['doctor', 'admin'],
    'diagnosis_completed': ['receptionist', 'admin'],
    'general': ['all'],
}


def create_notification(event_type, message, visit=None, target_role=None):
    """Create notification(s) for the appropriate roles."""
    targets = EVENT_TARGET_MAP.get(event_type, ['all'])
    if target_role:
        targets = [target_role]

    notifications = []
    for role in targets:
        n = Notification.objects.create(
            event_type=event_type,
            visit=visit,
            message=message,
            target_role=role,
        )
        notifications.append(n)
    return notifications
