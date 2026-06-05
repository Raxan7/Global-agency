"""
Custom template tags and filters for the project.
"""

from django import template
from django.utils.safestring import mark_safe

from globalagency_project.utils.security import safe_href

register = template.Library()


@register.filter(name='safe_href')
def safe_href_filter(value, fallback='#'):
    """
    Output a URL only when it uses a safe scheme (http, https, mailto, tel)
    or is a relative /media/ or /static/ path. Otherwise output *fallback*.
    Use this to defend against javascript: URIs in href attributes that come
    from user-controlled fields such as University.website.
    """
    cleaned = safe_href(value, fallback=fallback)
    return mark_safe(cleaned)
