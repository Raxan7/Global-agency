from django.urls import path
from . import views
from .password_reset_views import employee_forgot_password, employee_password_reset_confirm

app_name = 'employee'

urlpatterns = [
    path('login/', views.employee_login, name='employee_login'),
    path('dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('logout/', views.employee_logout, name='employee_logout'),
    
    # Password Reset
    path('forgot-password/', employee_forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', employee_password_reset_confirm, name='password_reset_employee_confirm'),
    
    # Africa Western Education applications
    path('applications/<int:pk>/', views.application_detail, name='application_detail'),
    
    # Student portal applications
    path('student-applications/', views.student_application_list, name='student_application_list'),
    path('student-applications/<int:application_id>/', views.student_application_detail, name='student_application_detail'),
    path('student-applications/<int:application_id>/update-status/', views.update_student_application_status, name='update_student_application_status'),
    
    # Payment Verification (M-PESA)
    path('student-applications/<int:application_id>/verify-payment/', views.verify_payment, name='verify_payment'),
    
    # PDF Export
    path('student-applications/<int:application_id>/export-pdf/', views.export_single_application_pdf, name='export_single_application_pdf'),
    path('student-applications/export-all-pdf/', views.export_all_applications_pdf, name='export_all_applications_pdf'),
    
    # Documents
    path('documents/', views.document_list, name='document_list'),
    
    # Contact messages
    path('contact-messages/', views.contact_messages, name='contact_messages'),
    path('contact-messages/<int:message_id>/update-status/', views.update_message_status, name='update_message_status'),
]