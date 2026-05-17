"""
context_processors.py  — MediCore HMS
──────────────────────────────────────
Injects two context variables into every template automatically:

  nav_sections   → filtered NAV_SECTIONS (sidebar)
  sitemap_data   → filtered SITEMAP_SECTIONS (hub page)

Both are filtered live on every request against the current user's role
properties.  A role change takes effect on the very next page load.

Register in settings.py:
    TEMPLATES[0]['OPTIONS']['context_processors'] += [
        'patients.context_processors.nav_context',
    ]
"""

from navmap import NAV_SECTIONS, SITEMAP_SECTIONS, ICONS
from django.urls import reverse, NoReverseMatch


def _resolve_url(item):
    """Resolve a nav item's URL safely — returns '#' if the URL doesn't exist yet."""
    if item.get('url_literal'):
        return item['url_literal']
    if item.get('url_name'):
        try:
            return reverse(item['url_name'])
        except NoReverseMatch:
            return '#'
    return '#'


def nav_context(request):
    """
    Called automatically on every request.
    Returns a dict that is merged into every template's context.
    """
    user = request.user

    if not user.is_authenticated:
        return {}

    # ── Build sidebar sections ─────────────────────────────────────────────
    sidebar = []
    for section in NAV_SECTIONS:
        if not section['check'](user):
            continue
        visible_items = []
        for item in section['items']:
            if not item['check'](user):
                continue
            visible_items.append({
                'label':     item['label'],
                'url':       _resolve_url(item),
                'icon_path': ICONS.get(item['icon'], ''),
                'nav_block': item.get('nav_block', ''),
                'badge_ctx': item.get('badge_ctx', ''),
            })
        if visible_items:
            sidebar.append({
                'label': section['label'],
                'items': visible_items,
            })

    # ── Build sitemap sections ─────────────────────────────────────────────
    sitemap = []
    for section in SITEMAP_SECTIONS:
        if not section['check'](user):
            continue
        visible_links = []
        for link in section['links']:
            if not link['check'](user):
                continue
            visible_links.append({
                'label': link['label'],
                'url':   _resolve_url(link),
            })
        sitemap.append({
            'title':       section['title'],
            'color':       section['color'],
            'icon_path':   ICONS.get(section['icon'], ''),
            'description': section['description'],
            'links':       visible_links,
        })

    return {
        'nav_sections': sidebar,
        'sitemap_data': sitemap,
    }