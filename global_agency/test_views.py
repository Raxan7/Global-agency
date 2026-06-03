"""Test view to debug locale middleware"""
from django.http import HttpResponse
from django.utils.translation import get_language
from django.conf import settings
from django.utils.html import format_html, mark_safe


def test_language_view(request):
    """View to test which language is detected"""
    current_lang = get_language()
    path = request.path
    get_lang = request.GET.get('lang', 'not in GET')
    session_lang = request.session.get(settings.LANGUAGE_SESSION_KEY, 'not in session')
    
    html = format_html(
        """
    <html>
    <head><title>Language Test</title></head>
    <body>
        <h1>Language Debug Info</h1>
        <p><strong>Request Path:</strong> {0}</p>
        <p><strong>Current Language (get_language()):</strong> {1}</p>
        <p><strong>GET Parameter (lang):</strong> {2}</p>
        <p><strong>Session Language:</strong> {3}</p>
        <p><strong>LANGUAGE_CODE Setting:</strong> {4}</p>
        <p><strong>All Available Languages:</strong></p>
        <ul>
            {5}
        </ul>
    </body>
    </html>
    """,
        path,
        current_lang,
        get_lang,
        session_lang,
        settings.LANGUAGE_CODE,
        mark_safe(''.join(format_html('<li><a href="/{0}/">Go to {1} ({0})</a></li>', code, name) for code, name in settings.LANGUAGES))
    )
    return HttpResponse(html)
