from django.db import transaction
from django.db.models import Max, F                      # ← Fixed: F imported at top
from django.utils import timezone
from .models import DepartmentQueue


def next_queue_number(department, date):
    """Thread-safe next queue number for a department on a given date."""
    result = DepartmentQueue.objects.filter(
        department=department, date=date
    ).aggregate(max_num=Max('queue_number'))
    return (result['max_num'] or 0) + 1


@transaction.atomic
def add_visit_to_queues(visit):
    """
    After payment confirmation, create a DepartmentQueue entry for every
    unique department referenced by the visit's services.
    Emergency visits are inserted at position 1 and existing entries bumped.
    """
    today = timezone.localdate()

    # Evaluate queryset to a list so we can reuse it (avoids re-querying in join)
    departments = list(
        visit.visit_services
        .values_list('service__department', flat=True)
        .distinct()
    )

    for dept in departments:
        if DepartmentQueue.objects.filter(visit=visit, department=dept).exists():
            continue  # Already queued — skip

        if visit.priority == 'emergency':
            # Bump all waiting entries in this dept today by 1
            DepartmentQueue.objects.filter(
                department=dept, date=today, status=DepartmentQueue.STATUS_WAITING
            ).update(queue_number=F('queue_number') + 1)   # ← Fixed: was models_F
            q_num = 1
        else:
            q_num = next_queue_number(dept, today)

        DepartmentQueue.objects.create(
            visit=visit,
            department=dept,
            queue_number=q_num,
            date=today,
        )

    # Update visit status to in_queue
    from patients.models import Visit as VisitModel
    visit.status = VisitModel.STATUS_IN_QUEUE
    visit.save(update_fields=['status'])

    # Notify doctors
    from notifications.utils import create_notification
    depts_str = ', '.join(departments)
    create_notification(
        event_type='patient_queued',
        visit=visit,
        message=f"{visit.patient.full_name} added to queue: {depts_str}",
    )