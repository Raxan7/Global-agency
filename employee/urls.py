from django.urls import path
from . import views
from .password_reset_views import employee_forgot_password, employee_password_reset_confirm

app_name = 'employee'

urlpatterns = [
    path('login/', views.employee_login, name='employee_login'),
    path('partners/login/', views.partner_login, name='partner_login'),
    path('partners/register/', views.partner_register, name='partner_register'),
    path('partners/activate/<uidb64>/<token>/', views.partner_activate, name='partner_activate'),
    path('partners/dashboard/', views.partner_dashboard, name='partner_dashboard'),
    path('partners/<int:profile_id>/approve/', views.approve_partner_account, name='approve_partner_account'),
    path('partners/logout/', views.partner_logout, name='partner_logout'),
    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('logout/', views.employee_logout, name='employee_logout'),
    
    # Password Reset
    path('forgot-password/', employee_forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', employee_password_reset_confirm, name='password_reset_employee_confirm'),
    
    # Africa Western Education applications
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    
    # Student portal applications
    path('student-applications/', views.student_application_list, name='student_application_list'),
    path('student-applications/offline/new/', views.offline_application_create, name='offline_application_create'),
    path('student-applications/<int:application_id>/', views.student_application_detail, name='student_application_detail'),
    path('student-applications/<int:application_id>/update-status/', views.update_student_application_status, name='update_student_application_status'),
    
    # Payment Verification (M-PESA)
    path('student-applications/<int:application_id>/verify-payment/', views.verify_payment, name='verify_payment'),
    
    # PDF Export
    path('student-applications/<int:application_id>/export-pdf/', views.export_single_application_pdf, name='export_single_application_pdf'),
    path('student-applications/export-all-pdf/', views.export_all_applications_pdf, name='export_all_applications_pdf'),
    
    # Documents
    path('documents/', views.document_list, name='document_list'),

    # Updates content management
    path('updates/', views.update_management, name='update_management'),
    path('updates/new/', views.update_create, name='update_create'),
    path('updates/<int:pk>/edit/', views.update_edit, name='update_edit'),
    path('updates/<int:pk>/delete/', views.update_delete, name='update_delete'),
    
    # Partner student records
    path('partners/students/new/', views.partner_application_create, name='partner_application_create'),
    path('partners/students/<int:pk>/edit/', views.partner_application_edit, name='partner_application_edit'),
    path('partners/students/<int:pk>/delete/', views.partner_application_delete, name='partner_application_delete'),
    
    # Contact messages
    path('contact-messages/', views.contact_messages, name='contact_messages'),
    path('contact-messages/<int:message_id>/update-status/', views.update_message_status, name='update_message_status'),
    path('contact-messages/<int:message_id>/reply/<str:channel>/', views.reply_to_message, name='reply_to_message'),
]
