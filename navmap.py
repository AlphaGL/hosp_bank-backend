"""
navmap.py  — MediCore HMS
─────────────────────────
Single source of truth for ALL navigation items across the system.

How permissions work
--------------------
Each nav item has a `check` callable that receives the `user` (Staff instance)
and returns True/False.  Because these are live callables evaluated on every
request, a role change takes effect the very next page load — nothing is
cached or hard-coded.

Adding a new role?
  1. Add an `is_<role>` property to the Staff model.
  2. Write a check below that references it.
  3. That's it — no other file needs to change.

Adding a new app / section?
  1. Append a new dict to NAV_SECTIONS.
  2. Add the same section to SITEMAP_SECTIONS if you want it on the hub page.
"""

# ─── Permission helpers ──────────────────────────────────────────────────────
# These are tiny lambdas so the navmap stays readable.
# Each returns True if the user should see that item.

def _all(u):          return u.is_authenticated
def _admin(u):        return getattr(u, 'is_admin', False)
def _receptionist(u): return getattr(u, 'is_receptionist', False) or getattr(u, 'is_admin', False)
def _finance(u):      return getattr(u, 'is_finance', False)      or getattr(u, 'is_admin', False)
def _doctor(u):       return getattr(u, 'is_doctor', False)       or getattr(u, 'is_admin', False)
def _nurse(u):        return getattr(u, 'is_nurse', False)        or getattr(u, 'is_admin', False)
def _lab(u):          return getattr(u, 'is_lab', False)          or getattr(u, 'is_admin', False)
def _pharmacy(u):     return getattr(u, 'is_pharmacy', False)     or getattr(u, 'is_admin', False)

# Inventory: store keepers, pharmacy, admin
def _inventory(u):
    return (
        getattr(u, 'is_pharmacy', False)
        or getattr(u, 'is_store_keeper', False)
        or getattr(u, 'is_admin', False)
    )

# Clinical: doctors + nurses + lab + admin
def _clinical(u):
    return (
        getattr(u, 'is_doctor', False)
        or getattr(u, 'is_nurse', False)
        or getattr(u, 'is_lab', False)
        or getattr(u, 'is_admin', False)
    )

# Patients section: receptionists, doctors, nurses, admin
def _patient_access(u):
    return (
        getattr(u, 'is_receptionist', False)
        or getattr(u, 'is_doctor', False)
        or getattr(u, 'is_nurse', False)
        or getattr(u, 'is_admin', False)
    )


# ─── SVG icon snippets (inline, no external deps) ───────────────────────────
ICONS = {
    'dashboard':    '<path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>',
    'patients':     '<path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>',
    'visits':       '<path d="M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm2 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>',
    'billing':      '<path d="M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z"/>',
    'inventory':    '<path d="M4 2h16l3 7v11c0 1.1-.9 2-2 2H3c-1.1 0-2-.9-2-2V9l3-7zm1 2l-1.8 4.2h17.6L19 4H5zm16 6H3v10h16V10zm-3 2v2H6v-2h12z"/>',
    'queue':        '<path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/>',
    'services':     '<path d="M19.5 12c0-4.14-3.36-7.5-7.5-7.5S4.5 7.86 4.5 12 7.86 19.5 12 19.5c1.43 0 2.76-.41 3.89-1.11l1.42 1.42A9.44 9.44 0 0112 21.5C6.75 21.5 2.5 17.25 2.5 12S6.75 2.5 12 2.5 21.5 6.75 21.5 12h-2zm-7-4v4.41l3.3 3.3-1.41 1.41-3.89-3.89V8h2z"/>',
    'staff':        '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>',
    'admin':        '<path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 4l5 2.18V11c0 3.5-2.33 6.79-5 7.93-2.67-1.14-5-4.43-5-7.93V7.18L12 5z"/>',
    'notifications':'<path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>',
    'reports':      '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/>',
    'discounts':    '<path d="M12.79 21L3 11.21v2c0 .53.21 1.04.59 1.41l7.79 7.79c.78.78 2.05.78 2.83 0l7.21-7.21c.78-.78.78-2.05 0-2.83L12.79 21zM11.38 17.41L3.59 9.62C3.21 9.24 3 8.74 3 8.21V4c0-1.1.9-2 2-2h4.21c.53 0 1.04.21 1.41.59l7.79 7.79c.78.78.78 2.05 0 2.83l-4.21 4.2c-.78.78-2.05.78-2.82 0zM6.5 8C7.33 8 8 7.33 8 6.5S7.33 5 6.5 5 5 5.67 5 6.5 5.67 8 6.5 8z"/>',
    'purchase':     '<path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96C5 16.1 6.1 17 7 17h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12L8.1 13h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49A1 1 0 0019.91 4H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2S15.9 22 17 22s2-.9 2-2-.9-2-2-2z"/>',
    'sitemap':      '<path d="M20 3H4v10c0 1.1.9 2 2 2h4v2H8v2h8v-2h-2v-2h4c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 10H6V5h14v8z"/>',
    'workload':     '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/>',
    'alert':        '<path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/>',
    'suppliers':    '<path d="M20 8h-3V4H3c-1.1 0-2 .9-2 2v11h2c0 1.66 1.34 3 3 3s3-1.34 3-3h6c0 1.66 1.34 3 3 3s3-1.34 3-3h2v-5l-3-4zM6 18.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm13.5-9l1.96 2.5H17V9.5h2.5zm-1.5 9c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/>',
    'movements':    '<path d="M7.5 21H2V9l5.5-6 5.5 6V21H7.5zm5-12.04V21H22V9l-5.5-6-4 4.62zM13 10h4v2h-4v-2zm0 4h4v2h-4v-2zm-5-4h4v2H8v-2zm0 4h4v2H8v-2z"/>',
}


# ─── NAV_SECTIONS: powers the sidebar ───────────────────────────────────────
#
# Structure:
#   label        → section heading shown in the sidebar
#   check        → callable(user) → bool — show this whole section?
#   items        → list of nav item dicts
#
# Each item:
#   label        → display text
#   url_name     → Django URL name (used with {% url %})
#   icon         → key into ICONS dict above
#   check        → callable(user) → bool
#   nav_block    → name of the {% block nav_X %} in base.html for active state
#   badge_ctx    → optional context variable name for the red badge count

NAV_SECTIONS = [
    {
        'label': 'Overview',
        'check': _all,
        'items': [
            {
                'label': 'Dashboard',
                'url_name': 'patients:dashboard',
                'icon': 'dashboard',
                'check': _all,
                'nav_block': 'nav_dashboard',
            },
            {
                'label': 'Navigation Hub',
                'url_name': 'sitemap:hub',
                'icon': 'sitemap',
                'check': _all,
                'nav_block': 'nav_sitemap',
            },
        ],
    },
    {
        'label': 'Patients & Visits',
        'check': _patient_access,
        'items': [
            {
                'label': 'Patients',
                'url_name': 'patients:patient-list',
                'icon': 'patients',
                'check': _patient_access,
                'nav_block': 'nav_patients',
            },
            {
                'label': 'Visits',
                'url_name': 'patients:visit-list',
                'icon': 'visits',
                'check': _patient_access,
                'nav_block': 'nav_visits',
            },
        ],
    },
    {
        'label': 'Clinical',
        'check': _clinical,
        'items': [
            {
                'label': 'Services',
                'url_name': 'services:list',
                'icon': 'services',
                'check': _clinical,
                'nav_block': 'nav_services',
            },
            {
                'label': 'Queue',
                'url_name': 'queues:list',
                'icon': 'queue',
                'check': _clinical,
                'nav_block': 'nav_queue',
            },
        ],
    },
    {
        'label': 'Billing',
        'check': _finance,
        'items': [
            {
                'label': 'Payments',
                'url_name': 'payments:list',
                'icon': 'billing',
                'check': _finance,
                'nav_block': 'nav_billing',
            },
            {
                'label': 'Discount Requests',
                'url_name': 'payments:discounts',
                'icon': 'discounts',
                'check': _finance,
                'nav_block': 'nav_discounts',
            },
        ],
    },
    {
        'label': 'Inventory / IMS',
        'check': _inventory,
        'items': [
            {
                'label': 'IMS Dashboard',
                'url_name': 'inventory:dashboard',
                'icon': 'inventory',
                'check': _inventory,
                'nav_block': 'nav_inventory',
            },
            {
                'label': 'Items',
                'url_name': 'inventory:item-list',
                'icon': 'reports',
                'check': _inventory,
                'nav_block': 'nav_items',
            },
            {
                'label': 'Stock Movements',
                'url_name': 'inventory:movement-list',
                'icon': 'movements',
                'check': _inventory,
                'nav_block': 'nav_movements',
            },
            {
                'label': 'Purchase Orders',
                'url_name': 'inventory:po-list',
                'icon': 'purchase',
                'check': _inventory,
                'nav_block': 'nav_po',
            },
            {
                'label': 'Suppliers',
                'url_name': 'inventory:supplier-list',
                'icon': 'suppliers',
                'check': _inventory,
                'nav_block': 'nav_suppliers',
            },
            {
                'label': 'Low Stock Alerts',
                'url_name': 'inventory:alerts',
                'icon': 'alert',
                'check': _inventory,
                'nav_block': 'nav_alerts',
            },
        ],
    },
    {
        'label': 'Notifications',
        'check': _all,
        'items': [
            {
                'label': 'Notifications',
                'url_name': 'notifications:list',
                'icon': 'notifications',
                'check': _all,
                'nav_block': 'nav_notifications',
                'badge_ctx': 'unread_count',
            },
        ],
    },
    {
        'label': 'Administration',
        'check': _admin,
        'items': [
            {
                'label': 'Staff',
                'url_name': 'patients:staff-list',
                'icon': 'staff',
                'check': _admin,
                'nav_block': 'nav_staff',
            },
            {
                'label': 'Workload Report',
                'url_name': 'department-workload',
                'icon': 'workload',
                'check': _admin,
                'nav_block': 'nav_workload',
            },
            {
                'label': 'Django Admin',
                'url_name': None,           # external link — handled in template
                'url_literal': '/admin/',
                'icon': 'admin',
                'check': _admin,
                'nav_block': 'nav_django_admin',
            },
        ],
    },
]


# ─── SITEMAP_SECTIONS: powers the visual hub page ───────────────────────────
#
# Each section has:
#   title        → card heading
#   color        → CSS variable name (from base.html palette)
#   icon         → key into ICONS
#   check        → callable(user) → bool — show this card at all?
#   links        → quick-action links shown inside the card

SITEMAP_SECTIONS = [
    {
        'title': 'Patients & Visits',
        'color': '--blue',
        'icon': 'patients',
        'check': _patient_access,
        'description': 'Register patients, manage visits, view history',
        'links': [
            {'label': 'Patient List',      'url_name': 'patients:patient-list',  'check': _patient_access},
            {'label': 'New Patient',       'url_name': 'patients:patient-create','check': _receptionist},
            {'label': 'All Visits',        'url_name': 'patients:visit-list',    'check': _patient_access},
            {'label': 'New Visit',         'url_name': 'patients:visit-create',  'check': _receptionist},
        ],
    },
    {
        'title': 'Clinical Services',
        'color': '--teal',
        'icon': 'services',
        'check': _clinical,
        'description': 'Manage diagnostic services, queues & results',
        'links': [
            {'label': 'Services List',     'url_name': 'services:list',          'check': _clinical},
            {'label': 'Department Queue',  'url_name': 'queues:list',            'check': _clinical},
            {'label': 'Workload View',     'url_name': 'department-workload',    'check': _clinical},
        ],
    },
    {
        'title': 'Billing & Payments',
        'color': '--success',
        'icon': 'billing',
        'check': _finance,
        'description': 'Process payments, receipts & discount approvals',
        'links': [
            {'label': 'All Payments',      'url_name': 'payments:list',          'check': _finance},
            {'label': 'Discount Requests', 'url_name': 'payments:discounts',     'check': _finance},
        ],
    },
    {
        'title': 'Inventory / IMS',
        'color': '--warn',
        'icon': 'inventory',
        'check': _inventory,
        'description': 'Stock, batches, purchase orders & dispensing',
        'links': [
            {'label': 'IMS Dashboard',     'url_name': 'inventory:dashboard',    'check': _inventory},
            {'label': 'Consumable Items',  'url_name': 'inventory:item-list',    'check': _inventory},
            {'label': 'Stock Movements',   'url_name': 'inventory:movement-list','check': _inventory},
            {'label': 'Purchase Orders',   'url_name': 'inventory:po-list',      'check': _inventory},
            {'label': 'Suppliers',         'url_name': 'inventory:supplier-list','check': _inventory},
            {'label': 'Low Stock Alerts',  'url_name': 'inventory:alerts',       'check': _inventory},
            {'label': 'Dispense Stock',    'url_name': 'inventory:dispense',     'check': _inventory},
        ],
    },
    {
        'title': 'Administration',
        'color': '--purple',
        'icon': 'admin',
        'check': _admin,
        'description': 'Staff management, system settings & Django admin',
        'links': [
            {'label': 'Staff Directory',   'url_name': 'patients:staff-list',    'check': _admin},
            {'label': 'Dashboard Summary', 'url_name': 'dashboard-summary',      'check': _admin},
            {'label': 'Django Admin',      'url_name': None, 'url_literal': '/admin/', 'check': _admin},
        ],
    },
    {
        'title': 'Notifications',
        'color': '--danger',
        'icon': 'notifications',
        'check': _all,
        'description': 'System alerts and in-app notifications',
        'links': [
            {'label': 'All Notifications', 'url_name': 'notifications:list',     'check': _all},
        ],
    },
]