from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import set_language
from django.contrib.sitemaps.views import sitemap
from django.views.generic import RedirectView
from globalagency_project.sitemap import sitemaps
from django.contrib.auth import views as auth_views  # ADD THIS IMPORT

# Non-localized URLs
urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('setlang/', set_language, name='set_language'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    
    # Direct app URLs (no language prefix by default - uses LANGUAGE_CODE='en')
    path('', include(('global_agency.urls', 'global_agency'))),
    path('employee/', include(('employee.urls', 'employee'))),
    path('student-portal/', include(('student_portal.urls', 'student_portal'))),
    
    # =============================================================================
    # PASSWORD RESET URLS FOR STUDENT PORTAL (ADDED)
    # =============================================================================
    
    # Password reset request - user enters email
    path('student-portal/password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='student_portal/password_reset.html',
             email_template_name='student_portal/password_reset_email.html',
             subject_template_name='student_portal/password_reset_subject.txt',
             success_url='/student-portal/password-reset/done/'
         ), name='student_password_reset'),
    
    # Password reset done - email sent confirmation
    path('student-portal/password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='student_portal/password_reset_done.html'
         ), name='student_password_reset_done'),
    
    # Password reset confirm - link from email (contains uid and token)
    path('student-portal/reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='student_portal/password_reset_confirm.html',
             success_url='/student-portal/reset/done/'
         ), name='student_password_reset_confirm'),
    
    # Password reset complete - success message
    path('student-portal/reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='student_portal/password_reset_complete.html'
         ), name='student_password_reset_complete'),
]

# Media and static files in DEBUG mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)