from django.urls import path
from . import views
from .password_reset_views import student_forgot_password, student_password_reset_confirm

app_name = 'student_portal'

urlpatterns = [
    path('', views.student_dashboard, name='dashboard'),
    path('login/', views.student_login, name='login'),
    path('logout/', views.student_logout, name='logout'),
    
    # Password Reset
    path('forgot-password/', student_forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', student_password_reset_confirm, name='password_reset_confirm'),
    
    # Profile
    path('profile/', views.student_profile, name='profile'),
    path('profile/personal-details/', views.personal_details, name='personal_details'),
    path('profile/parents-details/', views.parents_details, name='parents_details'),
    path('profile/academic-qualifications/', views.academic_qualifications, name='academic_qualifications'),
    path('profile/study-preferences/', views.study_preferences, name='study_preferences'),
    path('profile/emergency-contact/', views.emergency_contact, name='emergency_contact'),
    
    # WORK EXPERIENCE URLS
    path('work-experience/', views.work_experience_list, name='work_experience'),
    path('work-experience/add/', views.work_experience_add, name='work_experience_add'),
    path('work-experience/<int:pk>/edit/', views.work_experience_edit, name='work_experience_edit'),
    path('work-experience/<int:pk>/delete/', views.work_experience_delete, name='work_experience_delete'),
    
    # Applications
    path('applications/', views.applications, name='applications'),
    path('applications/<int:application_id>/', views.application_detail, name='application_detail'),
    path('applications/create/', views.create_application, name='create_application'),
    path('applications/<int:application_id>/payment/', views.payment_page, name='payment'),
    path('applications/<int:application_id>/make-payment/', views.make_payment, name='make_payment'),
    
    # Payment verification and webhooks
    path('payment/<int:payment_id>/verify/', views.payment_verification, name='payment_verification'),
    path('payment/<int:payment_id>/status/', views.check_payment_status_ajax, name='check_payment_status'),
    path('webhook/clickpesa/', views.clickpesa_webhook, name='clickpesa_webhook'),
    path('webhook/<str:provider>/', views.payment_webhook, name='payment_webhook'),
    
    # Documents
    path('documents/', views.documents, name='documents'),
    path('documents/services/', views.document_services, name='document_services'),
    path('documents/services/<str:service_type>/', views.service_form, name='service_form'),
    
    # Messages
    path('messages/', views.messages_list, name='messages'),
    path('messages/<int:message_id>/read/', views.mark_message_read, name='mark_message_read'),
]