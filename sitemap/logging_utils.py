"""
sitemap/logging_utils.py — MediCore HMS
────────────────────────────────────────
Two mechanisms for writing ActivityLog entries:

1. log_activity()  — explicit helper called from views/signals for rich entries
2. ActivityLogMiddleware — automatic HTTP-level logging (login, logout, key POSTs)

Usage in a view:
    from sitemap.logging_utils import log_activity
    from sitemap.models import ActivityLog

    log_activity(
        request,
        category=ActivityLog.CAT_BILLING,
        action='Payment confirmed',
        level=ActivityLog.LEVEL_SUCCESS,
        obj=payment,
        description=f'₦{payment.amount_paid} received for {payment.visit.patient.full_name}',
    )

Usage in signals (Django post_save etc.):
    log_activity(
        request=None,
        actor=staff_instance,
        category=ActivityLog.CAT_PATIENT,
        action='Patient registered',
        obj=patient,
    )
"""

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_ip(request):
    if not request:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_activity(
    request=None,
    actor=None,
    category='system',
    action='',
    description='',
    level='info',
    obj=None,
):
    """
    Create an ActivityLog entry.

    Parameters
    ----------
    request     : HttpRequest or None
    actor       : Staff instance or None (auto-resolved from request if omitted)
    category    : ActivityLog.CAT_* constant
    action      : short label string
    description : longer detail string
    level       : ActivityLog.LEVEL_* constant
    obj         : any Django model instance (for object_type / object_id / object_repr)
    """
    try:
        from sitemap.models import ActivityLog

        # Resolve actor from request if not supplied
        if actor is None and request is not None:
            u = getattr(request, 'user', None)
            if u and u.is_authenticated:
                actor = u

        kwargs = dict(
            actor=actor,
            category=category,
            action=action,
            description=description,
            level=level,
            ip_address=_get_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '')[:300] if request else ''),
            timestamp=timezone.now(),
        )

        if obj is not None:
            kwargs['object_type'] = obj.__class__.__name__
            kwargs['object_id']   = getattr(obj, 'pk', None)
            kwargs['object_repr'] = str(obj)[:200]

        ActivityLog.objects.create(**kwargs)

    except Exception as exc:
        # Logging must never crash the request
        logger.warning("ActivityLog write failed: %s", exc)


# ─── Middleware ───────────────────────────────────────────────────────────────

# URL fragments that should be auto-logged on POST
_POST_PATTERNS = [
    # (url_fragment,  category,          action,                    level)
    ('/login/',       'auth',     'User logged in',               'success'),
    ('/logout/',      'auth',     'User logged out',              'info'),
    ('/patients/new/',  'patient', 'Patient registered',          'success'),
    ('/visits/new/',    'visit',   'Visit created',               'success'),
    ('/confirm/',       'billing', 'Payment confirmed',           'success'),
    ('/request-discount/', 'discount', 'Discount requested',      'warning'),
    ('/discounts/',     'discount', 'Discount reviewed',          'info'),
    ('/dispense/',      'inventory','Stock dispensed',            'info'),
    ('/adjust/',        'inventory','Stock adjustment made',      'warning'),
    ('/po-receive/',    'inventory','Purchase order received',    'success'),
    ('/staff/new/',     'staff',    'Staff member created',       'success'),
]

_GET_PATTERNS = [
    ('/login/',   'auth', 'Login page viewed', 'info'),
]


class ActivityLogMiddleware:
    """
    Automatically logs key HTTP actions without any view changes needed.
    Register in settings.py MIDDLEWARE list (after SessionMiddleware):
        'sitemap.logging_utils.ActivityLogMiddleware',
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only log on successful responses (2xx / 3xx)
        if response.status_code >= 400:
            return response

        path = request.path

        # Skip static/media/admin-internal/API noise
        if any(path.startswith(p) for p in ('/static/', '/media/', '/api/', '/favicon')):
            return response

        try:
            if request.method == 'POST':
                for fragment, cat, action, level in _POST_PATTERNS:
                    if fragment in path:
                        log_activity(request=request, category=cat, action=action, level=level)
                        break
        except Exception:
            pass

        return response