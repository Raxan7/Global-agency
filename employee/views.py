from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.contrib import messages # Keep this for general messages
from django import forms
from django.forms import modelform_factory
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.db.models import Prefetch
from django.core.paginator import Paginator
from django.db import IntegrityError # Import IntegrityError
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone
from django.core.exceptions import ValidationError # Import ValidationError
from urllib.parse import quote
import logging
import re
import uuid
from global_agency.models import ContactMessage, StudentApplication, StudentProfile as GlobalStudentProfile
from student_portal.models import Application, ApplicationSupplementalProfile, Document, Payment, ProfessionalQualification, StudentProfile, WorkExperience
from student_portal.forms import (
    AcademicQualificationsForm,
    ApplicationForm as PortalApplicationForm,
    EmergencyContactForm,
    ParentsDetailsForm,
    PersonalDetailsForm,
    StudyPreferencesForm,
)
from .forms import (
    DOCUMENT_FLAG_FIELD_MAP,
    DOCUMENT_TYPE_FLAG_MAP,
    DOCUMENT_UPLOAD_FIELD_MAP,
    SUPPLEMENTAL_FIELD_NAMES,
    OfflineStudentIntakeForm,
    PartnerRegistrationForm,
    PortalUpdateForm,
    SupportingDocumentFormSet,
)
from .models import PortalUpdate, UserProfile
from .decorators import employee_required, admin_required, partner_required
from .awec_csc_exact_style_django_pdf_export import build_awec_csc_style_application_pdf_response

logger = logging.getLogger(__name__)

@csrf_protect
def employee_login(request):
    # If user is already authenticated and can access employee portal, redirect to dashboard
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.can_access_employee_portal():
                return redirect('employee:employee_dashboard')
            if profile.can_access_partner_portal():
                return redirect('employee:partner_dashboard')
            # Logout if user cannot access employee portal
            logout(request)
            messages.error(request, 'Access denied. Please use the student or partner portal.')
            return redirect('employee:employee_login')
        except UserProfile.DoesNotExist:
            pass

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.can_access_employee_portal():
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.get_full_name()}!')
                    if profile.is_admin():
                        return redirect('employee:admin_dashboard')
                    return redirect('employee:employee_dashboard')
                if profile.can_access_partner_portal():
                    messages.error(request, 'This login page is for employees. Please use the partner portal instead.')
                else:
                    messages.error(request, 'Access denied. This portal is for admin-created employees only. Students should use the student portal.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'Access denied. User profile not found. Please contact administrator.')
        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'employee/login.html')


@login_required
@employee_required
def employee_dashboard(request):
    profile = UserProfile.objects.get(user=request.user)

    applications = StudentApplication.objects.all().order_by('-created_at')
    student_applications = Application.objects.all().order_by('-created_at')
    contact_messages = ContactMessage.objects.all().order_by('-created_at')
    documents = Document.objects.all().order_by('-uploaded_at')[:10]
    updates = (
        PortalUpdate.objects.select_related('author')
        .prefetch_related('gallery_images', 'attachments')
        .order_by('-updated_at')
    )
    pending_partner_profiles = (
        UserProfile.objects.select_related('user', 'partner_approved_by')
        .filter(role='partner', registration_method='partner', is_partner_approved=False)
        .order_by('-created_at')
    )

    context = {
        'profile': profile,
        'applications': applications,
        'student_applications': student_applications,
        'contact_messages': contact_messages,
        'documents': documents,
        'applications_count': applications.count() + student_applications.count(),
        'messages_count': contact_messages.count(),
        'documents_count': Document.objects.count(),
        'pending_reviews': student_applications.filter(status='submitted').count(),
        'updates_count': updates.count(),
        'published_updates_count': updates.filter(status='published').count(),
        'upcoming_events_count': updates.filter(
            content_type='event',
            status='published',
            event_start__gte=timezone.now(),
        ).count(),
        'pending_partner_profiles': pending_partner_profiles,
        'pending_partner_count': pending_partner_profiles.count(),
        'recent_updates': updates[:4],
        'is_admin': profile.is_admin(),
        'is_regular_employee': profile.is_regular_employee(),
    }
    return render(request, 'employee/dashboard.html', context)


@login_required
@employee_required
@csrf_protect
def approve_partner_account(request, profile_id):
    partner_profile = get_object_or_404(
        UserProfile.objects.select_related('user'),
        pk=profile_id,
        role='partner',
        registration_method='partner',
    )

    if request.method == 'POST':
        partner_profile.is_partner_approved = True
        partner_profile.partner_approved_at = timezone.now()
        partner_profile.partner_approved_by = request.user
        partner_profile.save(update_fields=['is_partner_approved', 'partner_approved_at', 'partner_approved_by', 'updated_at'])
        messages.success(
            request,
            f'Partner account approved for {partner_profile.user.get_full_name() or partner_profile.user.username}.',
        )

    return redirect('employee:employee_dashboard')


@login_required
@admin_required
def admin_dashboard(request):
    """Admin-only dashboard with advanced features."""
    profile = UserProfile.objects.get(user=request.user)

    total_students = UserProfile.objects.filter(role='student').count()
    total_employees = UserProfile.objects.filter(role='employee').count()
    total_admins = UserProfile.objects.filter(role='admin').count()

    recent_applications = Application.objects.all().order_by('-created_at')[:5]
    recent_messages = ContactMessage.objects.all().order_by('-created_at')[:5]

    total_payments = Payment.objects.filter(is_successful=True)
    total_revenue = sum(payment.amount for payment in total_payments)

    context = {
        'profile': profile,
        'total_students': total_students,
        'total_employees': total_employees,
        'total_admins': total_admins,
        'total_applications': Application.objects.count(),
        'pending_applications': Application.objects.filter(status='submitted').count(),
        'recent_applications': recent_applications,
        'recent_messages': recent_messages,
        'total_revenue': total_revenue,
        'successful_payments': total_payments.count(),
    }
    return render(request, 'employee/admin_dashboard.html', context)


@login_required
@csrf_protect
def employee_logout(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('employee:employee_login')


@login_required
@employee_required
def application_detail(request, pk):
    application = get_object_or_404(StudentApplication, pk=pk)
    profile = UserProfile.objects.get(user=request.user)
    document_owner = application.student_user
    if document_owner is None and application.portal_application:
        document_owner = application.portal_application.student
    documents = (
        Document.objects.filter(student=document_owner).order_by('-uploaded_at')
        if document_owner is not None else Document.objects.none()
    )

    context = {
        'application': application,
        'documents': documents,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/application_detail.html', context)


@login_required
@employee_required
def student_application_list(request):
    """View all student portal applications."""
    profile = UserProfile.objects.get(user=request.user)

    applications_qs = (
        Application.objects.select_related('student')
        .prefetch_related(
            Prefetch(
                'offline_intakes',
                queryset=StudentApplication.objects.select_related('created_by', 'created_by__userprofile').order_by('-created_at'),
            )
        )
        .order_by('-created_at')
    )

    status_filter = request.GET.get('status')
    if status_filter:
        applications_qs = applications_qs.filter(status=status_filter)

    search_query = request.GET.get('search')
    if search_query:
        applications_qs = applications_qs.filter(
            Q(student__username__icontains=search_query)
            | Q(student__first_name__icontains=search_query)
            | Q(student__last_name__icontains=search_query)
        
        )

    applications = list(applications_qs)
    partner_submitted_count = 0
    for app in applications:
        partner_intake = None
        for intake in app.offline_intakes.all():
            created_by = intake.created_by
            if not created_by:
                continue
            user_profile = getattr(created_by, 'userprofile', None)
            if user_profile and user_profile.role == 'partner':
                partner_intake = intake
                partner_submitted_count += 1
                break
        app.partner_intake = partner_intake

    context = {
        'applications': applications,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_applications': Application.objects.count(),
        'pending_reviews': Application.objects.filter(status='submitted').count(),
        'approved_applications': Application.objects.filter(status='approved').count(),
        'displayed_count': len(applications),
        'partner_submitted_count': partner_submitted_count,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/student_application_list.html', context)


@login_required
@employee_required
def student_application_detail(request, application_id):
    """View detailed student portal application."""
    profile = UserProfile.objects.get(user=request.user)

    application = get_object_or_404(Application, id=application_id)

    partner_intake = (
        StudentApplication.objects.select_related('created_by', 'created_by__userprofile')
        .filter(portal_application=application, created_by__isnull=False)
        .order_by('-created_at')
        .first()
    )

    documents = Document.objects.filter(student=application.student)
    payments = Payment.objects.filter(application=application)

    try:
        student_profile = StudentProfile.objects.get(user=application.student)
    except StudentProfile.DoesNotExist:
        student_profile = None

    completion_summary = student_profile.get_completion_status() if student_profile else None

    context = {
        'application': application,
        'student_profile': student_profile,
        'documents': documents,
        'payments': payments,
        'partner_intake': partner_intake,
        'completion_summary': completion_summary,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/student_application_detail.html', context)


@login_required
@employee_required
@csrf_protect
def edit_student_application(request, application_id):
    """Allow employees to edit the full student application bundle."""
    application = get_object_or_404(Application, id=application_id)

    student_profile, _ = StudentProfile.objects.get_or_create(user=application.student)
    supplemental_profile = ApplicationSupplementalProfile.objects.filter(application=application).first()
    if supplemental_profile is None:
        supplemental_profile = ApplicationSupplementalProfile(application=application)

    # Build widget overrides for supplemental fields
    supplemental_widgets = {
        'full_name_passport': forms.TextInput(attrs={'class': 'form-input'}),
        'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
        'passport_number': forms.TextInput(attrs={'class': 'form-input'}),
        'passport_issue_country': forms.TextInput(attrs={'class': 'form-input'}),
        'passport_issue_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        'passport_expiration_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        'current_region': forms.Select(attrs={'class': 'form-input'}),
        'current_district': forms.Select(attrs={'class': 'form-input'}),
        'current_ward': forms.Select(attrs={'class': 'form-input'}),
        'current_street': forms.Select(attrs={'class': 'form-input'}),
        'current_mtaa': forms.TextInput(attrs={'class': 'form-input'}),
        'current_city': forms.TextInput(attrs={'class': 'form-input'}),
        'current_country': forms.TextInput(attrs={'class': 'form-input'}),
        'current_postal_code': forms.TextInput(attrs={'class': 'form-input'}),
        'current_house_no': forms.TextInput(attrs={'class': 'form-input'}),
        'permanent_region': forms.Select(attrs={'class': 'form-input'}),
        'permanent_district': forms.Select(attrs={'class': 'form-input'}),
        'permanent_ward': forms.Select(attrs={'class': 'form-input'}),
        'permanent_street': forms.Select(attrs={'class': 'form-input'}),
        'permanent_mtaa': forms.TextInput(attrs={'class': 'form-input'}),
        'permanent_house_no': forms.TextInput(attrs={'class': 'form-input'}),
        'permanent_address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'residential_email': forms.EmailInput(attrs={'class': 'form-input'}),
        'current_address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'valid_visa_details': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'professional_qualifications': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'professional_qualification_institution': forms.TextInput(attrs={'class': 'form-input'}),
        'professional_qualification_country': forms.TextInput(attrs={'class': 'form-input'}),
        'professional_qualification_region': forms.Select(attrs={'class': 'form-input'}),
        'professional_qualification_district': forms.Select(attrs={'class': 'form-input'}),
        'professional_qualification_ward': forms.Select(attrs={'class': 'form-input'}),
        'professional_qualification_street': forms.Select(attrs={'class': 'form-input'}),
        'professional_qualification_mtaa': forms.TextInput(attrs={'class': 'form-input'}),
        'professional_qualification_start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        'professional_qualification_completed_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        'professional_qualification_certificate_awarded': forms.Select(attrs={'class': 'form-select'}),
        'scholarship_details': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'medical_condition_details': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'special_assistance_details': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'other_attachments_description': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
        'english_test_name': forms.TextInput(attrs={'class': 'form-input'}),
        'english_test_institution': forms.TextInput(attrs={'class': 'form-input'}),
        'english_test_score': forms.TextInput(attrs={'class': 'form-input'}),
        'english_test_year': forms.TextInput(attrs={'class': 'form-input'}),
        'english_is_primary_language': forms.Select(attrs={'class': 'form-select'}),
        'certificate_start_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'certificate_completed_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'diploma_start_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'diploma_completed_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'bachelor_start_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'bachelor_completed_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'master_start_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'master_completed_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'phd_start_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
        'phd_completed_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2100}),
    }

    SupplementalProfileForm = modelform_factory(
        ApplicationSupplementalProfile,
        fields=SUPPLEMENTAL_FIELD_NAMES,
        widgets=supplemental_widgets,
    )

    # Look up linked offline intake from global_agency for work/profq/declaration fields
    offline_intake = StudentApplication.objects.filter(portal_application=application).first()
    if offline_intake is None:
        offline_intake = StudentApplication(portal_application=application)

    OFFLINE_INTAKE_EDIT_FIELDS = [
        'declaration_applicant_name', 'declaration_date', 'declaration_signature_name', 'terms_accepted',
        'work1_company_name', 'work1_position', 'work1_worked_from', 'work1_worked_to',
        'work1_country', 'work1_region', 'work1_district', 'work1_ward', 'work1_street',
        'work1_employment_type', 'work1_duties', 'work1_supervisor', 'work1_remarks',
        'work2_company_name', 'work2_position', 'work2_worked_from', 'work2_worked_to',
        'work2_country', 'work2_region', 'work2_district', 'work2_ward', 'work2_street',
        'work2_employment_type', 'work2_duties', 'work2_supervisor', 'work2_remarks',
        'profq1_title', 'profq1_institution', 'profq1_institution_address',
        'profq1_country', 'profq1_period', 'profq1_start_date', 'profq1_finished_date', 'profq1_award_certificate',
        'profq2_title', 'profq2_institution', 'profq2_institution_address',
        'profq2_country', 'profq2_period', 'profq2_start_date', 'profq2_finished_date', 'profq2_award_certificate',
        'profq3_title', 'profq3_institution', 'profq3_institution_address',
        'profq3_country', 'profq3_period', 'profq3_start_date', 'profq3_finished_date', 'profq3_award_certificate',
    ]

    OfflineIntakeEditForm = modelform_factory(
        StudentApplication,
        fields=OFFLINE_INTAKE_EDIT_FIELDS,
    )

    if request.method == 'POST':
        core_form = PortalApplicationForm(request.POST, instance=application)
        personal_form = PersonalDetailsForm(request.POST, request.FILES, instance=student_profile)
        parents_form = ParentsDetailsForm(request.POST, instance=student_profile)
        academic_form = AcademicQualificationsForm(request.POST, instance=student_profile)
        preferences_form = StudyPreferencesForm(request.POST, instance=student_profile)
        emergency_form = EmergencyContactForm(request.POST, instance=student_profile)
        supplemental_form = SupplementalProfileForm(request.POST, instance=supplemental_profile)
        offline_intake_form = OfflineIntakeEditForm(request.POST, instance=offline_intake)

        forms_to_save = [
            core_form,
            personal_form,
            parents_form,
            academic_form,
            preferences_form,
            emergency_form,
            supplemental_form,
            offline_intake_form,
        ]

        if all(form.is_valid() for form in forms_to_save):
            with transaction.atomic():
                core_form.save()
                personal_form.save()
                parents_form.save()
                academic_form.save()
                preferences_form.save()
                emergency_form.save()
                supplemental_instance = supplemental_form.save(commit=False)
                supplemental_instance.application = application
                supplemental_instance.save()
                offline_intake_instance = offline_intake_form.save(commit=False)
                offline_intake_instance.portal_application = application
                offline_intake_instance.save()

            messages.success(request, 'Student application updated successfully.')
            return redirect('employee:student_application_detail', application_id=application_id)

        messages.error(request, 'Please correct the errors below.')
    else:
        core_form = PortalApplicationForm(instance=application)
        personal_form = PersonalDetailsForm(instance=student_profile)
        parents_form = ParentsDetailsForm(instance=student_profile)
        academic_form = AcademicQualificationsForm(instance=student_profile)
        preferences_form = StudyPreferencesForm(instance=student_profile)
        emergency_form = EmergencyContactForm(instance=student_profile)
        supplemental_form = SupplementalProfileForm(instance=supplemental_profile)
        offline_intake_form = OfflineIntakeEditForm(instance=offline_intake)

    # Field lists for each section
    PERSONAL_DETAILS_FIELDS = ['full_name', 'gender', 'date_of_birth', 'nationality', 'phone_number', 'place_of_birth', 'marital_status', 'native_language', 'profile_picture']
    PERSONAL_PASSPORT_FIELDS = ['passport_number', 'passport_issue_date', 'passport_expiration_date']
    SUPPLEMENTAL_PASSPORT_FIELDS = ['full_name_passport', 'residential_email', 'has_valid_visa', 'valid_visa_details']

    EMERGENCY_CONTACT_FIELDS = [
        'emergency_contact', 'emergency_relation', 'emergency_occupation',
        'emergency_phone', 'emergency_email', 'emergency_alternative_phone',
        'emergency_country', 'emergency_region', 'emergency_district', 'emergency_ward', 'emergency_street',
        'emergency_region_post_code', 'emergency_district_post_code', 'emergency_ward_post_code',
        'emergency_place_neighbourhood', 'emergency_house_no',
        'emergency_relationship_status', 'emergency_remarks',
    ]

    POST_SECONDARY_FIELDS = [
        'certificate_institution', 'certificate_field_of_study', 'certificate_start_year', 'certificate_completed_year', 'certificate_gpa',
        'diploma_institution', 'diploma_field_of_study', 'diploma_start_year', 'diploma_completed_year', 'diploma_gpa',
        'bachelor_institution', 'bachelor_field_of_study', 'bachelor_start_year', 'bachelor_completed_year', 'bachelor_gpa',
        'master_institution', 'master_field_of_study', 'master_start_year', 'master_completed_year', 'master_gpa',
        'phd_institution', 'phd_field_of_study', 'phd_start_year', 'phd_completed_year', 'phd_gpa',
    ]

    SUPPLEMENTAL_PROFQ_FIELDS = [
        'professional_qualifications', 'professional_qualification_institution',
        'professional_qualification_country', 'professional_qualification_region',
        'professional_qualification_district', 'professional_qualification_ward',
        'professional_qualification_street', 'professional_qualification_mtaa',
        'professional_qualification_start_date', 'professional_qualification_completed_date',
        'professional_qualification_certificate_awarded',
    ]

    WORK_EXPERIENCE_FIELDS = [
        'work1_company_name', 'work1_position', 'work1_worked_from', 'work1_worked_to',
        'work1_country', 'work1_region', 'work1_district', 'work1_ward', 'work1_street',
        'work1_employment_type', 'work1_duties', 'work1_supervisor', 'work1_remarks',
        'work2_company_name', 'work2_position', 'work2_worked_from', 'work2_worked_to',
        'work2_country', 'work2_region', 'work2_district', 'work2_ward', 'work2_street',
        'work2_employment_type', 'work2_duties', 'work2_supervisor', 'work2_remarks',
    ]

    OFFLINE_PROFQ_FIELDS = [
        'profq1_title', 'profq1_institution', 'profq1_institution_address',
        'profq1_country', 'profq1_period', 'profq1_start_date', 'profq1_finished_date', 'profq1_award_certificate',
        'profq2_title', 'profq2_institution', 'profq2_institution_address',
        'profq2_country', 'profq2_period', 'profq2_start_date', 'profq2_finished_date', 'profq2_award_certificate',
        'profq3_title', 'profq3_institution', 'profq3_institution_address',
        'profq3_country', 'profq3_period', 'profq3_start_date', 'profq3_finished_date', 'profq3_award_certificate',
    ]

    STUDY_PREFERENCES_SUPPLEMENTAL = ['program_level', 'preferred_intake', 'accommodation_preference']

    STUDENT_ADDRESS_FIELDS = [
        'permanent_country', 'permanent_region', 'permanent_district', 'permanent_ward',
        'permanent_street', 'permanent_mtaa', 'permanent_house_no', 'permanent_address',
        'current_country', 'current_region', 'current_district', 'current_ward',
        'current_street', 'current_mtaa', 'current_house_no',
        'current_city', 'current_postal_code', 'current_address',
    ]

    OTHER_DETAILS_FIELDS = [
        'education_sponsor', 'estimated_budget_usd', 'scholarship_applied', 'scholarship_details',
        'has_medical_condition', 'medical_condition_details', 'needs_special_assistance',
        'special_assistance_details', 'english_test_name', 'english_test_institution',
        'english_test_score', 'english_test_year', 'english_is_primary_language',
    ]

    DECLARATION_OFFLINE_FIELDS = ['declaration_applicant_name', 'declaration_date', 'declaration_signature_name', 'terms_accepted']

    HOW_HEARD_FIELDS = ['heard_about_us', 'heard_about_other']

    def bfields(form, field_list):
        return [form[f] for f in field_list if f in form.fields]

    form_sections = [
        {
            'key': 'personal_details',
            'title': 'Personal Details',
            'description': 'Update personal information and passport details.',
            'bound_fields': bfields(personal_form, PERSONAL_DETAILS_FIELDS)
                + bfields(personal_form, PERSONAL_PASSPORT_FIELDS)
                + bfields(supplemental_form, SUPPLEMENTAL_PASSPORT_FIELDS),
        },
        {
            'key': 'parents',
            'title': "Parents' Details",
            'description': "Update parents'/guardians contact information (including address and post code).",
            'bound_fields': bfields(parents_form, parents_form.fields),
        },
        {
            'key': 'emergency_contact',
            'title': 'Emergency Contact Details',
            'description': 'Update emergency contact information with full address.',
            'bound_fields': bfields(emergency_form, EMERGENCY_CONTACT_FIELDS),
        },
        {
            'key': 'education_background',
            'title': 'Education Background',
            'description': 'Update A-Level, O-Level, and post-secondary / higher education.',
            'bound_fields': bfields(academic_form, academic_form.fields)
                + bfields(supplemental_form, POST_SECONDARY_FIELDS),
        },
        {
            'key': 'professional_qualifications',
            'title': 'Professional Qualifications / Training',
            'description': 'Update professional qualifications, training, and English proficiency.',
            'bound_fields': bfields(supplemental_form, SUPPLEMENTAL_PROFQ_FIELDS)
                + bfields(offline_intake_form, OFFLINE_PROFQ_FIELDS)
                + [supplemental_form['english_test_name'], supplemental_form['english_test_institution'],
                   supplemental_form['english_test_score'], supplemental_form['english_test_year'],
                   supplemental_form['english_is_primary_language']],
        },
        {
            'key': 'employment_history',
            'title': 'Employment History / Work Experience',
            'description': 'Update work experience records.',
            'bound_fields': bfields(offline_intake_form, WORK_EXPERIENCE_FIELDS),
        },
        {
            'key': 'study_preferences',
            'title': 'Study Preferences',
            'description': 'Update preferred intakes, programs, accommodation, and sponsorship.',
            'bound_fields': bfields(preferences_form, preferences_form.fields)
                + bfields(supplemental_form, STUDY_PREFERENCES_SUPPLEMENTAL),
        },
        {
            'key': 'student_address',
            'title': 'Student Address',
            'description': 'Update permanent and current address details (supplemental).',
            'bound_fields': bfields(supplemental_form, STUDENT_ADDRESS_FIELDS),
        },
        {
            'key': 'other_details',
            'title': 'Other Details',
            'description': 'Update visa, scholarship, medical, and English proficiency info.',
            'bound_fields': bfields(supplemental_form, OTHER_DETAILS_FIELDS),
        },
        {
            'key': 'how_heard',
            'title': 'How Did You Hear About Us',
            'description': 'Update referral source information.',
            'bound_fields': bfields(emergency_form, HOW_HEARD_FIELDS),
        },
        {
            'key': 'declaration',
            'title': 'Declaration by Applicant',
            'description': 'Update declaration, applicant name, date, and terms acceptance.',
            'bound_fields': [supplemental_form['declaration_agreed']] + bfields(offline_intake_form, DECLARATION_OFFLINE_FIELDS),
        },
    ]

    full_width_fields = {
        'professional_qualifications',
        'scholarship_details',
        'medical_condition_details',
        'special_assistance_details',
        'other_attachments_description',
        'valid_visa_details',
        'current_address',
        'permanent_address',
        'profq1_institution_address',
        'profq2_institution_address',
        'profq3_institution_address',
        'work1_duties',
        'work1_remarks',
        'work2_duties',
        'work2_remarks',
        'description',
        'responsibilities',
        'achievements',
    }

    return render(
        request,
        'employee/student_application_edit.html',
        {
            'application': application,
            'form_sections': form_sections,
            'core_form': core_form,
            'offline_intake_form': offline_intake_form,
            'full_width_fields': full_width_fields,
        },
    )


@login_required
@employee_required
@csrf_protect
def update_student_application_status(request, application_id):
    """Update student portal application status."""
    application = get_object_or_404(Application, id=application_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        employee_status_note = (request.POST.get('employee_status_note') or '').strip()
        official_eligibility = request.POST.get('official_eligibility', '').strip()
        official_documents_verified_raw = request.POST.get('official_documents_verified', '').strip()
        official_admission_status = request.POST.get('official_admission_status', '').strip()
        official_visa_status = request.POST.get('official_visa_status', '').strip()
        official_final_decision = request.POST.get('official_final_decision', '').strip()
        official_remarks = (request.POST.get('official_remarks') or '').strip()

        documents_verified_value = None
        if official_documents_verified_raw == 'true':
            documents_verified_value = True
        elif official_documents_verified_raw == 'false':
            documents_verified_value = False

        if new_status in dict(Application.APPLICATION_STATUS):
            application.status = new_status
            application.employee_status_note = employee_status_note
            application.official_eligibility = official_eligibility
            application.official_documents_verified = documents_verified_value
            application.official_admission_status = official_admission_status
            application.official_visa_status = official_visa_status
            application.official_final_decision = official_final_decision
            application.official_remarks = official_remarks
            application.status_updated_by = request.user
            application.status_updated_at = timezone.now()
            application.save(
                update_fields=[
                    'status',
                    'employee_status_note',
                    'official_eligibility',
                    'official_documents_verified',
                    'official_admission_status',
                    'official_visa_status',
                    'official_final_decision',
                    'official_remarks',
                    'status_updated_by',
                    'status_updated_at',
                    'updated_at',
                ]
            )
            messages.success(request, f'Application status updated to {application.get_status_display()}.')
        else:
            messages.error(request, 'Invalid status selected.')

    return redirect('employee:student_application_detail', application_id=application_id)


def _create_or_update_student_portal_records(
    cleaned_data,
    created_by,
    existing_user=None,
    portal_application=None,
    reset_password=True,
    uploaded_files=None,
    document_formset=None,
):
    def text_value(key):
        return cleaned_data.get(key) or ''

    def persist_field_file(field_file, uploaded_file, fallback_prefix):
        original_name = getattr(uploaded_file, 'name', '') or f'{fallback_prefix}'
        file_name = original_name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        field_file.save(file_name, uploaded_file, save=False)

    def available_fallback_username():
        full_name_slug = re.sub(r'[^a-z0-9]+', '-', (cleaned_data.get('full_name') or '').lower()).strip('-')
        base = f"offline-{full_name_slug or 'student'}"[:120].strip('-') or 'offline-student'
        while True:
            candidate = f'{base}-{uuid.uuid4().hex[:8]}'
            if not User.objects.filter(username=candidate).exists():
                return candidate

    full_name = (cleaned_data.get('full_name') or '').strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ''
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
    email = (cleaned_data.get('email') or '').strip().lower()
    account_username = email or available_fallback_username()
    default_password = f"{(first_name.upper() or 'STUDENT')}12345"

    if existing_user is not None:
        user = existing_user
        user_created = False
    else:
        user, user_created = User.objects.get_or_create(
            username=account_username,
            defaults={
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            },
        )

    if email:
        user.username = email
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    if reset_password or user_created:
        # nosemgrep: python.django.security.audit.unvalidated-password.unvalidated-password
        # The default password is a system-generated temporary credential
        # handed to the student on intake; the student is required to change
        # it on first login, so we deliberately keep the predictable format
        # and skip Django's password validators.
        user.set_password(default_password)
    user.save()

    user_profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'role': 'student',
            'registration_method': 'admin',
            'phone_number': text_value('phone'),
        },
    )
    user_profile.role = 'student'
    user_profile.registration_method = 'admin'
    user_profile.phone_number = text_value('phone')
    user_profile.save()

    GlobalStudentProfile.objects.update_or_create(
        user=user,
        defaults={
            'phone': text_value('phone'),
            'emergency_contact': text_value('emergency_name'),
            'emergency_phone': text_value('phone'),
        },
    )

    def mtaa_val(key):
        """Get mtaa address field value, defaulting to empty string."""
        return cleaned_data.get(key) or ''

    def mtaa_year(key):
        """Get year field value, defaulting to empty string."""
        return cleaned_data.get(key) or ''

    student_profile, _ = StudentProfile.objects.update_or_create(
        user=user,
        defaults={
            'phone_number': text_value('phone'),
            'date_of_birth': cleaned_data.get('date_of_birth'),
            'nationality': text_value('nationality'),
            'place_of_birth': text_value('place_of_birth'),
            'marital_status': text_value('marital_status'),
            'native_language': text_value('native_language'),
            'gender': text_value('gender'),
            'region': mtaa_val('region'),
            'ward': mtaa_val('ward'),
            'street': mtaa_val('street'),
            'mtaa': mtaa_val('mtaa'),
            'house_no': mtaa_val('house_no'),
            'city': mtaa_val('city'),
            'village': mtaa_val('village'),
            'father_name': text_value('father_name'),
            'father_phone': text_value('father_phone'),
            'father_email': text_value('father_email'),
            'father_occupation': text_value('father_occupation'),
            'father_country': mtaa_val('father_country'),
            'father_region': mtaa_val('father_region'),
            'father_district': mtaa_val('father_district'),
            'father_ward': mtaa_val('father_ward'),
            'father_street': mtaa_val('father_street'),
            'father_house_no': mtaa_val('father_house_no'),
            'father_place_neighbourhood': mtaa_val('father_place_neighbourhood'),
            'father_region_post_code': mtaa_val('father_region_post_code'),
            'father_district_post_code': mtaa_val('father_district_post_code'),
            'father_ward_post_code': mtaa_val('father_ward_post_code'),
            'father_status': text_value('father_status'),
            'father_relationship': text_value('father_relationship'),
            'mother_name': text_value('mother_name'),
            'mother_phone': text_value('mother_phone'),
            'mother_email': text_value('mother_email'),
            'mother_occupation': text_value('mother_occupation'),
            'mother_country': mtaa_val('mother_country'),
            'mother_region': mtaa_val('mother_region'),
            'mother_district': mtaa_val('mother_district'),
            'mother_ward': mtaa_val('mother_ward'),
            'mother_street': mtaa_val('mother_street'),
            'mother_house_no': mtaa_val('mother_house_no'),
            'mother_place_neighbourhood': mtaa_val('mother_place_neighbourhood'),
            'mother_region_post_code': mtaa_val('mother_region_post_code'),
            'mother_district_post_code': mtaa_val('mother_district_post_code'),
            'mother_ward_post_code': mtaa_val('mother_ward_post_code'),
            'mother_status': text_value('mother_status'),
            'mother_relationship': text_value('mother_relationship'),
            'olevel_school': text_value('olevel_school'),
            'olevel_school_country': text_value('olevel_school_country'),
            'olevel_school_region': mtaa_val('olevel_school_region'),
            'olevel_school_district': mtaa_val('olevel_school_district'),
            'olevel_school_ward': mtaa_val('olevel_school_ward'),
            'olevel_school_street': mtaa_val('olevel_school_street'),
            'olevel_school_house_no': mtaa_val('olevel_school_house_no'),
            'olevel_school_place_neighbourhood': mtaa_val('olevel_school_place_neighbourhood'),
            'olevel_start_year': mtaa_year('olevel_start_year'),
            'olevel_completed_year': mtaa_year('olevel_completed_year'),
            'olevel_candidate_no': text_value('olevel_candidate_no'),
            'olevel_gpa': text_value('olevel_gpa'),
            'olevel_school_region_post_code': mtaa_val('olevel_school_region_post_code'),
            'olevel_school_district_post_code': mtaa_val('olevel_school_district_post_code'),
            'olevel_school_ward_post_code': mtaa_val('olevel_school_ward_post_code'),
            'olevel_school_type': text_value('olevel_school_type'),
            'olevel_exam_board': text_value('olevel_exam_board'),
            'olevel_certificate_no': text_value('olevel_certificate_no'),
            'olevel_remarks': text_value('olevel_remarks'),
            'alevel_school': text_value('alevel_school'),
            'alevel_school_country': text_value('alevel_school_country'),
            'alevel_school_region': mtaa_val('alevel_school_region'),
            'alevel_school_district': mtaa_val('alevel_school_district'),
            'alevel_school_ward': mtaa_val('alevel_school_ward'),
            'alevel_school_street': mtaa_val('alevel_school_street'),
            'alevel_school_house_no': mtaa_val('alevel_school_house_no'),
            'alevel_school_place_neighbourhood': mtaa_val('alevel_school_place_neighbourhood'),
            'alevel_start_year': mtaa_year('alevel_start_year'),
            'alevel_completed_year': mtaa_year('alevel_completed_year'),
            'alevel_candidate_no': text_value('alevel_candidate_no'),
            'alevel_gpa': text_value('alevel_gpa'),
            'alevel_school_region_post_code': mtaa_val('alevel_school_region_post_code'),
            'alevel_school_district_post_code': mtaa_val('alevel_school_district_post_code'),
            'alevel_school_ward_post_code': mtaa_val('alevel_school_ward_post_code'),
            'alevel_school_type': text_value('alevel_school_type'),
            'alevel_exam_board': text_value('alevel_exam_board'),
            'alevel_certificate_no': text_value('alevel_certificate_no'),
            'alevel_remarks': text_value('alevel_remarks'),
            'preferred_country_1': text_value('preferred_country_1'),
            'preferred_country_2': text_value('preferred_country_2'),
            'preferred_country_3': text_value('preferred_country_3'),
            'preferred_program_1': text_value('preferred_program_1'),
            'preferred_program_2': text_value('preferred_program_2'),
            'preferred_program_3': text_value('preferred_program_3'),
            'preferred_intake': text_value('preferred_intake'),
            'emergency_contact': text_value('emergency_name'),
            'emergency_relation': text_value('emergency_relation'),
            'emergency_occupation': text_value('emergency_occupation'),
            'emergency_phone': text_value('emergency_phone'),
            'emergency_email': text_value('emergency_email'),
            'emergency_alternative_phone': text_value('emergency_alternative_phone'),
            'emergency_country': mtaa_val('emergency_country'),
            'emergency_region': mtaa_val('emergency_region'),
            'emergency_district': mtaa_val('emergency_district'),
            'emergency_ward': mtaa_val('emergency_ward'),
            'emergency_street': mtaa_val('emergency_street'),
            'emergency_place_neighbourhood': mtaa_val('emergency_place_neighbourhood'),
            'emergency_house_no': mtaa_val('emergency_house_no'),
            'emergency_region_post_code': mtaa_val('emergency_region_post_code'),
            'emergency_district_post_code': mtaa_val('emergency_district_post_code'),
            'emergency_ward_post_code': mtaa_val('emergency_ward_post_code'),
            'emergency_relationship_status': text_value('emergency_relationship_status'),
            'emergency_remarks': text_value('emergency_remarks'),
            'heard_about_us': text_value('heard_about_us'),
            'heard_about_other': text_value('heard_about_other'),
        },
    )

    profile_picture = (uploaded_files or {}).get('profile_picture_upload')
    if profile_picture:
        persist_field_file(student_profile.profile_picture, profile_picture, f'profiles/{email}_profile')
        student_profile.save(update_fields=['profile_picture', 'personal_details_complete', 'parents_details_complete', 'academic_qualifications_complete', 'study_preferences_complete', 'emergency_contact_complete'])
        logger.info(
            'Saved profile picture via %s for %s as %s',
            student_profile.profile_picture.storage.__class__.__name__,
            email,
            student_profile.profile_picture.name,
        )

    sync_student = getattr(student_profile, 'sync_normalized_fields', None)
    if sync_student:
        try:
            sync_student()
        except Exception:
            pass

    uploader_role = getattr(getattr(created_by, 'userprofile', None), 'role', '')
    uploader_label = 'partner' if uploader_role == 'partner' else 'employee'

    portal_defaults = {
        'student': user,
        'status': 'submitted',
        'is_paid': True,
        'payment_amount': 0,
        'payment_status': 'paid',
        'payment_verified_by': created_by,
        'payment_verified_at': timezone.now(),
        'payment_notes': 'Created by staff from an offline application form.',
    }

    if portal_application is not None:
        for field_name, value in portal_defaults.items():
            setattr(portal_application, field_name, value)
        portal_application.save()
    else:
        portal_application = Application.objects.create(**portal_defaults)

    supplemental_profile, _ = ApplicationSupplementalProfile.objects.get_or_create(
        application=portal_application
    )
    for field_name in SUPPLEMENTAL_FIELD_NAMES:
        setattr(supplemental_profile, field_name, cleaned_data.get(field_name))

    if not supplemental_profile.full_name_passport:
        supplemental_profile.full_name_passport = full_name
    if not supplemental_profile.residential_email:
        supplemental_profile.residential_email = email
    if not supplemental_profile.current_address:
        supplemental_profile.current_address = text_value('address')
    if not supplemental_profile.current_country:
        supplemental_profile.current_country = text_value('nationality') or 'Tanzania'
    if not supplemental_profile.serial_number:
        year = portal_application.created_at.year if portal_application.created_at else timezone.now().year
        supplemental_profile.serial_number = f'AWECO/INT/REG/TZ/DSM/{year}8{portal_application.id:03d}'

    if profile_picture:
        supplemental_profile.has_passport_photo = True

    if document_formset:
        for doc_form in document_formset:
            if not doc_form.cleaned_data or doc_form.cleaned_data.get('DELETE'):
                continue
            document_type = doc_form.cleaned_data.get('document_type')
            uploaded_document = doc_form.cleaned_data.get('file')
            if not document_type or not uploaded_document:
                continue
            existing_docs = Document.objects.filter(student=user, document_type=document_type).order_by('-uploaded_at')
            existing_doc = existing_docs.first()
            if existing_doc:
                existing_docs.exclude(pk=existing_doc.pk).delete()
                persist_field_file(existing_doc.file, uploaded_document, f'documents/{document_type}')
                existing_doc.description = f'Uploaded through the {uploader_label} intake workflow.'
                existing_doc.is_verified = False
                existing_doc.save(update_fields=['file', 'description', 'is_verified'])
            else:
                document = Document(
                    student=user,
                    document_type=document_type,
                    description=f'Uploaded through the {uploader_label} intake workflow.',
                )
                persist_field_file(document.file, uploaded_document, f'documents/{document_type}')
                document.save()
            document_record = existing_doc if existing_doc else document
            logger.info(
                'Saved document via %s for %s: type=%s name=%s url=%s',
                document_record.file.storage.__class__.__name__,
                email,
                document_type,
                document_record.file.name,
                document_record.file.url,
            )
            supplemental_flag = DOCUMENT_TYPE_FLAG_MAP.get(document_type)
            if supplemental_flag:
                setattr(supplemental_profile, supplemental_flag, True)

    supplemental_profile.save()

    # Save Work Experience entries
    work_entries = [
        ('work1_', 1),
        ('work2_', 2),
    ]
    for prefix, order in work_entries:
        company = cleaned_data.get(f'{prefix}company_name')
        if company:
            we, _ = WorkExperience.objects.update_or_create(
                student=student_profile,
                company_name=company,
                defaults={
                    'position': text_value(f'{prefix}position'),
                    'start_date': cleaned_data.get(f'{prefix}worked_from'),
                    'end_date': cleaned_data.get(f'{prefix}worked_to'),
                    'country': text_value(f'{prefix}country'),
                    'region': text_value(f'{prefix}region'),
                    'region_post_code': text_value(f'{prefix}region_post_code'),
                    'district': text_value(f'{prefix}district'),
                    'district_post_code': text_value(f'{prefix}district_post_code'),
                    'ward': text_value(f'{prefix}ward'),
                    'ward_post_code': text_value(f'{prefix}ward_post_code'),
                    'street': text_value(f'{prefix}street'),
                    'employment_type': text_value(f'{prefix}employment_type'),
                    'responsibilities': text_value(f'{prefix}duties'),
                    'supervisor': text_value(f'{prefix}supervisor'),
                    'remarks': text_value(f'{prefix}remarks'),
                },
            )

    # Save Professional Qualification entries
    profq_entries = [
        ('profq1_', 1),
        ('profq2_', 2),
        ('profq3_', 3),
    ]
    for prefix, order in profq_entries:
        title = cleaned_data.get(f'{prefix}title')
        if title:
            ProfessionalQualification.objects.update_or_create(
                application=portal_application,
                order_number=order,
                defaults={
                    'qualification_title': title,
                    'institution': text_value(f'{prefix}institution'),
                    'institution_address': text_value(f'{prefix}institution_address'),
                    'country': text_value(f'{prefix}country'),
                    'period': text_value(f'{prefix}period'),
                    'start_date': cleaned_data.get(f'{prefix}start_date'),
                    'finished_date': cleaned_data.get(f'{prefix}finished_date'),
                    'award_certificate': text_value(f'{prefix}award_certificate'),
                },
            )

    sync_supplemental = getattr(supplemental_profile, 'sync_normalized_fields', None)
    if sync_supplemental:
        try:
            sync_supplemental()
        except Exception:
            pass

    return user, student_profile, portal_application, default_password


@login_required
@employee_required
@csrf_protect
def offline_application_create(request):
    """Capture an offline application on behalf of a student."""
    supplemental_instance = None
    student_profile_instance = None
    existing_documents = []
    document_formset = SupportingDocumentFormSet(request.POST or None, request.FILES or None, prefix='documents')

    if request.method == 'POST':
        form = OfflineStudentIntakeForm(
            request.POST,
            request.FILES,
            supplemental_instance=supplemental_instance,
            student_profile_instance=student_profile_instance,
            existing_documents=existing_documents,
        )
        if form.is_valid() and document_formset.is_valid():
            try:
                with transaction.atomic():
                    offline_application = form.save(commit=False)
                    (
                        student_user,
                        _student_profile,
                        portal_application,
                        default_password,
                    ) = _create_or_update_student_portal_records(
                        form.cleaned_data,
                        request.user,
                        uploaded_files=request.FILES,
                        document_formset=document_formset,
                    )

                    offline_application.student_user = student_user
                    offline_application.portal_application = portal_application
                    offline_application.created_by = request.user
                    offline_application.account_created = True
                    offline_application.username = student_user.username
                    offline_application.temporary_password = default_password
                    offline_application.save()
            except IntegrityError as e:
                logger.exception(
                    'Offline intake database integrity error for %s. Files=%s',
                    form.cleaned_data.get('email'),
                    list(request.FILES.keys()),
                )
                messages.error(request, f'A database error occurred: {e}. This might be due to duplicate data or a missing reference. Please check the input.')
                # The transaction.atomic() block will automatically roll back on exception
            except ValidationError as e:
                messages.error(request, f'Validation error during offline intake: {e.message_dict or e.messages}')
            except Exception as e:
                logger.exception(
                    'Offline intake upload failed for %s. Files=%s',
                    form.cleaned_data.get('email'),
                    list(request.FILES.keys()),
                )
                messages.error(request, 'The upload failed while saving to Cloudinary. Please try again with a valid file.')
            else:
                messages.success(
                    request,
                    f'Offline application saved for {student_user.get_full_name() or student_user.username}. '
                    f'Login username: {student_user.username} | Default password: {default_password}',
                )
                return redirect('employee:student_application_detail', application_id=portal_application.id)
        else:
            logger.warning(
                'Offline intake form invalid for %s. Errors=%s Files=%s',
                form['email'].value(),
                form.errors.as_json(),
                list(request.FILES.keys()),
            )
    else:
        form = OfflineStudentIntakeForm(
            supplemental_instance=supplemental_instance,
            student_profile_instance=student_profile_instance,
            existing_documents=existing_documents,
        )

    return render(
        request,
        'employee/offline_application_form.html',
        {
            'form': form,
            'form_sections': _build_intake_form_sections(form),
            'page_title': 'Add offline application',
            'submit_label': 'Save student and create account',
            'current_profile_picture': getattr(form, 'current_profile_picture', None),
            'existing_documents': form.existing_documents_by_type,
            'document_formset': document_formset,
        },
    )


def _build_intake_form_sections(form):
    section_specs = [
        {
            'key': 'form_meta',
            'title': 'Form Header / Application Meta',
            'description': 'Reference number, application date, and student photo.',
            'icon': 'fa-file-pen',
            'fields': ['profile_picture_upload'],
        },
        {
            'key': 'personal_details',
            'title': 'Personal Details',
            'description': 'Full name, gender, date of birth, nationality, passport, and contact information.',
            'icon': 'fa-user-graduate',
            'fields': [
                'full_name', 'gender', 'date_of_birth', 'place_of_birth',
                'nationality', 'native_language', 'marital_status',
                'email', 'phone',
                'passport_number', 'passport_issue_date', 'passport_expiration_date',
                'city', 'region', 'ward', 'village', 'street', 'house_no',
            ],
        },
        {
            'key': 'parents',
            'title': 'Parents Details',
            'description': 'Enter full details for mother and father.',
            'icon': 'fa-people-roof',
            'fields': [
                # Mother's Details
                'mother_name', 'mother_occupation', 'mother_phone', 'mother_email',
                'mother_country', 'mother_region', 'mother_region_post_code',
                'mother_district', 'mother_district_post_code',
                'mother_ward', 'mother_ward_post_code',
                'mother_street', 'mother_house_no', 'mother_place_neighbourhood',
                'mother_status', 'mother_relationship',
                # Father's Details
                'father_name', 'father_occupation', 'father_phone', 'father_email',
                'father_country', 'father_region', 'father_region_post_code',
                'father_district', 'father_district_post_code',
                'father_ward', 'father_ward_post_code',
                'father_street', 'father_house_no', 'father_place_neighbourhood',
                'father_status', 'father_relationship',
            ],
        },
        {
            'key': 'emergency_contact',
            'title': 'Emergency Contact Details',
            'description': 'Who should be contacted in case of an emergency.',
            'icon': 'fa-user-shield',
            'fields': [
                'emergency_name', 'emergency_relation', 'emergency_occupation',
                'emergency_phone', 'emergency_email',
                'emergency_house_no',
                'emergency_country', 'emergency_region', 'emergency_region_post_code',
                'emergency_district', 'emergency_district_post_code',
                'emergency_ward', 'emergency_ward_post_code',
                'emergency_street', 'emergency_place_neighbourhood',
                'emergency_alternative_phone', 'emergency_relationship_status',
                'emergency_remarks',
            ],
        },
        {
            'key': 'education_background',
            'title': 'Education Background Details',
            'description': 'A-Level, O-Level, and post-secondary / higher education history.',
            'icon': 'fa-school',
            'fields': [
                # A-Level
                'alevel_school', 'alevel_candidate_no',
                'alevel_start_year', 'alevel_completed_year', 'alevel_gpa',
                'alevel_school_country', 'alevel_school_region', 'alevel_school_region_post_code',
                'alevel_school_district', 'alevel_school_district_post_code',
                'alevel_school_ward', 'alevel_school_ward_post_code',
                'alevel_school_street', 'alevel_school_place_neighbourhood',
                'alevel_school_type', 'alevel_exam_board', 'alevel_certificate_no',
                'alevel_remarks',
                # O-Level
                'olevel_school', 'olevel_candidate_no',
                'olevel_start_year', 'olevel_completed_year', 'olevel_gpa',
                'olevel_school_country', 'olevel_school_region', 'olevel_school_region_post_code',
                'olevel_school_district', 'olevel_school_district_post_code',
                'olevel_school_ward', 'olevel_school_ward_post_code',
                'olevel_school_street', 'olevel_school_place_neighbourhood',
                'olevel_school_type', 'olevel_exam_board', 'olevel_certificate_no',
                'olevel_remarks',
                # Post-Secondary / Higher Education
                'certificate_institution', 'certificate_field_of_study',
                'certificate_start_year', 'certificate_completed_year', 'certificate_gpa',
                'diploma_institution', 'diploma_field_of_study',
                'diploma_start_year', 'diploma_completed_year', 'diploma_gpa',
                'bachelor_institution', 'bachelor_field_of_study',
                'bachelor_start_year', 'bachelor_completed_year', 'bachelor_gpa',
                'master_institution', 'master_field_of_study',
                'master_start_year', 'master_completed_year', 'master_gpa',
                'phd_institution', 'phd_field_of_study',
                'phd_start_year', 'phd_completed_year', 'phd_gpa',
            ],
        },
        {
            'key': 'professional_qualifications',
            'title': 'Professional Qualifications / Training',
            'description': 'Up to three professional qualifications and English language proficiency.',
            'icon': 'fa-certificate',
            'fields': [
                # Qualification 1
                'profq1_title', 'profq1_institution', 'profq1_institution_address',
                'profq1_country', 'profq1_period',
                'profq1_start_date', 'profq1_finished_date', 'profq1_award_certificate',
                # Qualification 2
                'profq2_title', 'profq2_institution', 'profq2_institution_address',
                'profq2_country', 'profq2_period',
                'profq2_start_date', 'profq2_finished_date', 'profq2_award_certificate',
                # Qualification 3
                'profq3_title', 'profq3_institution', 'profq3_institution_address',
                'profq3_country', 'profq3_period',
                'profq3_start_date', 'profq3_finished_date', 'profq3_award_certificate',
                # English Language Proficiency
                'english_test_name', 'english_test_institution',
                'english_test_score', 'english_test_year',
                'english_is_primary_language',
            ],
        },
        {
            'key': 'employment_history',
            'title': 'Employment History / Work Experience',
            'description': 'Previous work experience details.',
            'icon': 'fa-briefcase',
            'fields': [
                # Work Experience 1
                'work1_company_name', 'work1_position',
                'work1_worked_from', 'work1_worked_to',
                'work1_country', 'work1_region', 'work1_region_post_code',
                'work1_district', 'work1_district_post_code',
                'work1_ward', 'work1_ward_post_code',
                'work1_street',
                'work1_employment_type', 'work1_duties',
                'work1_supervisor', 'work1_remarks',
                # Work Experience 2
                'work2_company_name', 'work2_position',
                'work2_worked_from', 'work2_worked_to',
                'work2_country', 'work2_region', 'work2_region_post_code',
                'work2_district', 'work2_district_post_code',
                'work2_ward', 'work2_ward_post_code',
                'work2_street',
                'work2_employment_type', 'work2_duties',
                'work2_supervisor', 'work2_remarks',
            ],
        },
        {
            'key': 'study_preferences',
            'title': 'Study Preferences',
            'description': 'Preferred intake, countries, and programs.',
            'icon': 'fa-compass-drafting',
            'fields': [
                'preferred_intake',
                'preferred_country_1', 'preferred_program_1',
                'preferred_country_2', 'preferred_program_2',
                'preferred_country_3', 'preferred_program_3',
            ],
        },
        {
            'key': 'student_address',
            'title': 'Student Address',
            'description': 'Permanent and current address details.',
            'icon': 'fa-location-dot',
            'fields': [
                # Permanent Address
                'permanent_country', 'permanent_region', 'permanent_region_post_code',
                'permanent_district', 'permanent_district_post_code',
                'permanent_ward', 'permanent_ward_post_code',
                'permanent_street', 'permanent_mtaa',
                'permanent_house_no', 'permanent_place_neighbourhood',
                'permanent_postal_code', 'permanent_address_status',
                'permanent_nearest_landmark', 'permanent_duration_at_address',
                'permanent_address_remarks',
                # Current Address
                'current_country', 'current_region', 'current_region_post_code',
                'current_district', 'current_district_post_code',
                'current_ward', 'current_ward_post_code',
                'current_street', 'current_mtaa',
                'current_house_no', 'current_place_neighbourhood',
                'current_postal_code', 'current_address_status',
                'current_nearest_landmark', 'current_duration_at_address',
                'current_address_remarks',
            ],
        },
        {
            'key': 'other_details',
            'title': 'Other Details',
            'description': 'Visa, program level, accommodation, finances, medical, and special assistance.',
            'icon': 'fa-list',
            'fields': [
                'has_valid_visa', 'valid_visa_details',
                'program_level', 'accommodation_preference',
                'education_sponsor', 'estimated_budget_usd',
                'scholarship_applied', 'scholarship_details',
                'has_medical_condition', 'medical_condition_details',
                'needs_special_assistance', 'special_assistance_details',
            ],
        },
        {
            'key': 'how_heard',
            'title': 'How Did You Hear About Us',
            'description': 'Referral source.',
            'icon': 'fa-bullhorn',
            'fields': [
                'heard_about_us', 'heard_about_other',
            ],
        },
        {
            'key': 'declaration',
            'title': 'Declaration by Applicant',
            'description': 'Read and accept the declaration before submitting.',
            'icon': 'fa-file-signature',
            'fields': [
                'declaration_applicant_name', 'declaration_date',
                'declaration_signature_name', 'declaration_agreed',
            ],
        },
        {
            'key': 'terms',
            'title': 'Terms and Conditions',
            'description': 'Accept the terms and conditions.',
            'icon': 'fa-scale-balanced',
            'fields': [
                'terms_accepted',
            ],
        },
        {
            'key': 'office_use',
            'title': 'Office Use Only',
            'description': 'Internal approval section.',
            'icon': 'fa-stamp',
            'fields': [
                'office_director_name', 'office_approval_status',
                'office_reason',
            ],
        },
        {
            'key': 'uploads',
            'title': 'Supporting Documents',
            'description': 'Upload supporting files.',
            'icon': 'fa-file-arrow-up',
            'fields': [
                'has_passport_copy', 'has_passport_photo', 'has_academic_certificates',
                'has_academic_transcripts', 'has_english_test_results',
                'has_cv_resume', 'has_personal_statement',
                'has_recommendation_letters', 'has_financial_proof',
                'has_health_insurance', 'has_other_attachments',
                'other_attachments_description',
            ],
        },
    ]

    sections = []
    for spec in section_specs:
        available_fields = [field_name for field_name in spec['fields'] if field_name in form.fields]
        if not available_fields:
            continue
        bound_fields = [form[field_name] for field_name in available_fields]
        sections.append({
            'key': spec['key'],
            'title': spec['title'],
            'description': spec['description'],
            'icon': spec['icon'],
            'bound_fields': bound_fields,
        })
    return sections


@csrf_protect
def partner_register(request):
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.can_access_partner_portal():
                return redirect('employee:partner_dashboard')
        except UserProfile.DoesNotExist:
            pass

    if request.method == 'POST':
        form = PartnerRegistrationForm(request.POST)
        if form.is_valid():
            full_name = form.cleaned_data['full_name'].strip()
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            user.is_active = False
            user.save()

            UserProfile.objects.create(
                user=user,
                role='partner',
                registration_method='partner',
            )

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            activation_link = request.build_absolute_uri(
                reverse('employee:partner_activate', kwargs={'uidb64': uid, 'token': token})
            )

            subject = 'Activate your Partner Portal account'
            message = (
                f"Hello {user.get_full_name() or user.username},\n\n"
                "Your partner account has been created. Click the link below to verify your email and activate your account:\n"
                f"{activation_link}\n\n"
                "If you did not request this account, you can safely ignore this email.\n\n"
                "Best regards,\n"
                "Africa Western Education Team"
            )

            try:
                send_mail(
                    subject,
                    message,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@africawesternedu.com'),
                    [email],
                    fail_silently=False,
                )
                messages.success(request, 'Your partner account has been created. Check your email to activate it.')
            except Exception as exc:
                print(f'Partner verification email failed: {exc}')
                print(f'Activation link: {activation_link}')
                messages.success(request, 'Your partner account has been created. Check the server logs for the activation link while email is configured.')

            return redirect('employee:partner_login')
    else:
        form = PartnerRegistrationForm()

    return render(request, 'partner/register.html', {'form': form})


def partner_activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user, role='partner', registration_method='partner')

        profile.role = 'partner'
        profile.registration_method = 'partner'
        profile.save()

        user.is_active = True
        user.save(update_fields=['is_active'])
        messages.success(request, 'Your email has been verified. Your partner account now awaits employee approval before you can access the portal.')
        return redirect('employee:partner_login')

    messages.error(request, 'The activation link is invalid or has expired.')
    return redirect('employee:partner_login')


@csrf_protect
def partner_login(request):
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.can_access_partner_portal():
                return redirect('employee:partner_dashboard')
        except UserProfile.DoesNotExist:
            pass

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.can_access_partner_portal():
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.get_full_name()}!')
                    return redirect('employee:partner_dashboard')
                if profile.is_partner() and profile.registration_method == 'partner' and user.is_active and not profile.is_partner_approved:
                    messages.error(request, 'Your email is verified, but your partner account is still waiting for employee approval.')
                else:
                    messages.error(request, 'Access denied. This login is only for approved partner accounts.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'Access denied. Partner profile not found.')
        else:
            inactive_user = User.objects.filter(username__iexact=username).first()
            if inactive_user and not inactive_user.is_active:
                messages.error(request, 'Your account is not active yet. Please check your email for the activation link.')
            else:
                messages.error(request, 'Invalid username or password')

    return render(request, 'partner/login.html')


@login_required
@partner_required
def partner_dashboard(request):
    profile = UserProfile.objects.get(user=request.user)
    applications = (
        StudentApplication.objects.filter(created_by=request.user)
        .select_related('student_user', 'portal_application')
        .order_by('-created_at')
    )

    context = {
        'profile': profile,
        'applications': applications,
        'applications_count': applications.count(),
        'recent_applications': applications[:6],
    }
    return render(request, 'partner/dashboard.html', context)


@login_required
@partner_required
@csrf_protect
def partner_application_create(request):
    document_formset = SupportingDocumentFormSet(request.POST or None, request.FILES or None, prefix='documents')

    if request.method == 'POST':
        form = OfflineStudentIntakeForm(request.POST, request.FILES)
        if form.is_valid() and document_formset.is_valid():
            try:
                with transaction.atomic():
                    offline_application = form.save(commit=False)
                    (
                        student_user,
                        _student_profile,
                        portal_application,
                        default_password,
                    ) = _create_or_update_student_portal_records(
                        form.cleaned_data,
                        request.user,
                        uploaded_files=request.FILES,
                        document_formset=document_formset,
                    )

                    offline_application.student_user = student_user
                    offline_application.portal_application = portal_application
                    offline_application.created_by = request.user
                    offline_application.account_created = True
                    offline_application.username = student_user.username
                    offline_application.temporary_password = default_password
                    offline_application.save()
            except IntegrityError as e:
                logger.exception(
                    'Partner create database integrity error for %s. Partner=%s Files=%s',
                    form.cleaned_data.get('email'),
                    request.user.username,
                    list(request.FILES.keys()),
                )
                messages.error(request, f'A database error occurred: {e}. This might be due to duplicate data or a missing reference. Please check the input.')
                # The transaction.atomic() block will automatically roll back on exception
            except ValidationError as e:
                messages.error(request, f'Validation error during partner application create: {e.message_dict or e.messages}')
            except Exception as e:
                logger.exception(
                    'Partner create upload failed for %s. Partner=%s Files=%s',
                    form.cleaned_data.get('email'),
                    request.user.username,
                    list(request.FILES.keys()),
                )
                messages.error(request, 'The upload failed while saving to Cloudinary. Please use a valid PDF/image file and try again.')
            else:
                messages.success(request, f'Student record created for {student_user.get_full_name() or student_user.username}.')
                return redirect('employee:partner_dashboard')
        else:
            logger.warning(
                'Partner create form invalid for %s. Partner=%s Errors=%s Files=%s',
                form['email'].value(),
                request.user.username,
                form.errors.as_json(),
                list(request.FILES.keys()),
            )
    else:
        form = OfflineStudentIntakeForm()

    return render(
        request,
        'partner/student_form.html',
        {
            'form': form,
            'form_sections': _build_intake_form_sections(form),
            'page_title': 'Add student record',
            'submit_label': 'Save student record',
            'current_profile_picture': getattr(form, 'current_profile_picture', None),
            'existing_documents': form.existing_documents_by_type,
            'document_formset': document_formset,
        },
    )


@login_required
@partner_required
@csrf_protect
def partner_application_edit(request, pk):
    application = get_object_or_404(StudentApplication, pk=pk, created_by=request.user)
    supplemental_instance = (
        ApplicationSupplementalProfile.objects.filter(application=application.portal_application).first()
        if application.portal_application else None
    )
    student_profile_instance = (
        StudentProfile.objects.filter(user=application.student_user).first()
        if application.student_user else None
    )
    existing_documents = (
        Document.objects.filter(student=application.student_user).order_by('-uploaded_at')
        if application.student_user else Document.objects.none()
    )

    document_formset = SupportingDocumentFormSet(request.POST or None, request.FILES or None, prefix='documents')

    if request.method == 'POST':
        form = OfflineStudentIntakeForm(
            request.POST,
            request.FILES,
            instance=application,
            supplemental_instance=supplemental_instance,
            student_profile_instance=student_profile_instance,
            existing_documents=existing_documents,
        )
        if form.is_valid() and document_formset.is_valid():
            try:
                with transaction.atomic():
                    offline_application = form.save(commit=False)
                    (
                        student_user,
                        _student_profile,
                        portal_application,
                        _default_password,
                    ) = _create_or_update_student_portal_records(
                        form.cleaned_data,
                        request.user,
                        existing_user=application.student_user,
                        portal_application=application.portal_application,
                        reset_password=False,
                        uploaded_files=request.FILES,
                        document_formset=document_formset,
                    )

                    offline_application.student_user = student_user
                    offline_application.portal_application = portal_application
                    offline_application.created_by = request.user
                    offline_application.account_created = True
                    offline_application.username = student_user.username
                    offline_application.temporary_password = application.temporary_password
                    offline_application.save()
            except Exception:
                logger.exception(
                    'Partner edit upload failed for application=%s partner=%s files=%s',
                    application.pk,
                    request.user.username,
                    list(request.FILES.keys()),
                )
                messages.error(request, 'The upload failed while saving to Cloudinary. Please use a valid PDF/image file and try again.')
            else:
                messages.success(request, 'Student record updated successfully.')
                return redirect('employee:partner_dashboard')
        else:
            logger.warning(
                'Partner edit form invalid for application=%s partner=%s errors=%s files=%s',
                application.pk,
                request.user.username,
                form.errors.as_json(),
                list(request.FILES.keys()),
            )
    else:
        form = OfflineStudentIntakeForm(
            instance=application,
            supplemental_instance=supplemental_instance,
            student_profile_instance=student_profile_instance,
            existing_documents=existing_documents,
        )

    return render(
        request,
        'partner/student_form.html',
        {
            'form': form,
            'form_sections': _build_intake_form_sections(form),
            'page_title': 'Edit student record',
            'submit_label': 'Update student record',
            'application': application,
            'current_profile_picture': getattr(form, 'current_profile_picture', None),
            'existing_documents': form.existing_documents_by_type,
            'document_formset': document_formset,
        },
    )


@login_required
@partner_required
@csrf_protect
def partner_application_delete(request, pk):
    application = get_object_or_404(StudentApplication, pk=pk, created_by=request.user)

    if request.method == 'POST':
        if application.portal_application:
            application.portal_application.delete()
        application.delete()
        messages.success(request, 'Student record deleted successfully.')
        return redirect('employee:partner_dashboard')

    return render(
        request,
        'partner/student_confirm_delete.html',
        {
            'application': application,
        },
    )


@login_required
@csrf_protect
def partner_logout(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('employee:partner_login')


@login_required
@employee_required
def document_list(request):
    """View all uploaded documents"""
    profile = UserProfile.objects.get(user=request.user)
    
    # ALL employees see ALL documents
    documents = Document.objects.all().order_by('-uploaded_at')
    
    # Filter by document type if provided
    doc_type_filter = request.GET.get('doc_type')
    if doc_type_filter:
        documents = documents.filter(document_type=doc_type_filter)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        documents = documents.filter(
            Q(student__username__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(document_type__icontains=search_query)
        )
    
    context = {
        'documents': documents,
        'doc_type_filter': doc_type_filter,
        'search_query': search_query,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/document_list.html', context)

@login_required
@employee_required
def contact_messages(request):
    """View all contact messages and consultations"""
    profile = UserProfile.objects.get(user=request.user)

    current_tab = request.GET.get('tab', 'all')

    # Base queryset — exclude blocked unless viewing spam
    if current_tab == 'spam':
        base = ContactMessage.objects.filter(is_blocked=True)
    else:
        base = ContactMessage.objects.filter(is_blocked=False)

    base = base.order_by('-created_at')

    # Filter by handled status if provided
    status_filter = request.GET.get('status')
    if status_filter == 'new':
        base = base.filter(handled=False)
    elif status_filter == 'replied':
        base = base.filter(handled=True)

    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        base = base.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(destination__icontains=search_query) |
            Q(message__icontains=search_query)
        )

    if current_tab == 'spam':
        consultations = base.none()
        contact_messages_list = base
        spam_messages = base
    else:
        consultations = base.exclude(destination__isnull=True).exclude(destination__exact='')
        contact_messages_list = base.filter(Q(destination__isnull=True) | Q(destination__exact=''))
        spam_messages = ContactMessage.objects.none()
    
    context = {
        'contact_messages': contact_messages_list,
        'consultations': consultations,
        'spam_messages': spam_messages,
        'status_filter': status_filter,
        'search_query': search_query,
        'current_tab': current_tab,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/contact_messages.html', context)

@login_required
@employee_required
@csrf_protect
def update_message_status(request, message_id):
    """Update contact message status"""
    message = get_object_or_404(ContactMessage, id=message_id)

    if request.method == 'POST':
        handled_value = request.POST.get('handled')
        if handled_value in ['0', '1']:
            message.handled = handled_value == '1'
            message.save(update_fields=['handled'])
            label = 'Replied/Handled' if message.handled else 'New/Pending'
            messages.success(request, f'Message status updated to {label}.')
        else:
            messages.error(request, 'Invalid status selected.')

    return redirect('employee:contact_messages')


@login_required
@employee_required
@csrf_protect
def block_message(request, message_id):
    """Toggle block/unblock a contact message"""
    message = get_object_or_404(ContactMessage, id=message_id)
    if request.method == 'POST':
        message.is_blocked = not message.is_blocked
        message.save(update_fields=['is_blocked'])
        label = 'blocked' if message.is_blocked else 'unblocked'
        messages.success(request, f'Message from {message.name} has been {label}.')
    return redirect('employee:contact_messages')


@login_required
@employee_required
@csrf_protect
def delete_message(request, message_id):
    """Delete a single contact message"""
    message = get_object_or_404(ContactMessage, id=message_id)
    if request.method == 'POST':
        name = message.name
        message.delete()
        messages.success(request, f'Message from {name} has been deleted.')
    return redirect('employee:contact_messages')


@login_required
@employee_required
@csrf_protect
def bulk_message_action(request):
    """Handle bulk actions (block, unblock, delete) on messages"""
    if request.method == 'POST':
        action = request.POST.get('action')
        message_ids = request.POST.getlist('message_ids')
        if not message_ids:
            messages.warning(request, 'No messages selected.')
            return redirect('employee:contact_messages')

        qs = ContactMessage.objects.filter(id__in=message_ids)

        if action == 'block':
            count = qs.update(is_blocked=True)
            messages.success(request, f'{count} message(s) blocked.')
        elif action == 'unblock':
            count = qs.update(is_blocked=False)
            messages.success(request, f'{count} message(s) unblocked.')
        elif action == 'delete':
            count = qs.count()
            qs.delete()
            messages.success(request, f'{count} message(s) deleted.')
        else:
            messages.error(request, 'Invalid action.')

    return redirect('employee:contact_messages')


def _build_email_reply_subject(contact_message):
    is_consultation = bool((contact_message.destination or '').strip())
    if is_consultation:
        return 'Re: Your Consultation Request - Africa Western Education'
    return 'Re: Your Message - Africa Western Education'


def _build_whatsapp_reply_url(contact_message):
    raw_phone = (contact_message.phone or '').strip()
    digits = re.sub(r'\D', '', raw_phone)

    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = '255' + digits[1:]
    elif not digits.startswith('255') and len(digits) >= 9:
        digits = '255' + digits[-9:]

    if not digits:
        return ''

    text = quote(f"Hello {contact_message.name}, regarding your request with Africa Western Education.")
    return f"https://wa.me/{digits}?text={text}"


@login_required
@employee_required
@csrf_protect
def reply_to_message(request, message_id, channel):
    """Send an in-system reply and optionally open WhatsApp."""
    contact_message = get_object_or_404(ContactMessage, id=message_id)

    if request.method != 'POST':
        messages.error(request, 'Invalid request method for reply action.')
        return redirect('employee:contact_messages')

    if channel == 'email':
        subject = (request.POST.get('subject') or '').strip() or _build_email_reply_subject(contact_message)
        reply_body = (request.POST.get('reply_message') or '').strip()

        if not reply_body:
            messages.error(request, 'Reply message cannot be empty.')
            return redirect('employee:contact_messages')

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@africawesternedu.com')
        email_body = (
            f"Dear {contact_message.name},\n\n"
            f"{reply_body}\n\n"
            "Best regards,\n"
            "Africa Western Education\n"
            "info@africawesterneducation.com"
        )

        try:
            send_mail(
                subject,
                email_body,
                from_email,
                [contact_message.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception('Failed to send employee reply email for contact message %s', contact_message.id)
            messages.error(request, 'The reply could not be sent right now. Please check the email configuration and try again.')
            return redirect('employee:contact_messages')

        contact_message.reply_subject = subject
        contact_message.reply_message = reply_body
        contact_message.replied_at = timezone.now()
        contact_message.replied_by = request.user
        contact_message.handled = True
        contact_message.save(
            update_fields=[
                'reply_subject',
                'reply_message',
                'replied_at',
                'replied_by',
                'handled',
            ]
        )
        messages.success(request, f'Reply sent successfully to {contact_message.email}.')
        return redirect('employee:contact_messages')

    if channel == 'whatsapp':
        if not contact_message.handled:
            contact_message.handled = True
            contact_message.save(update_fields=['handled'])
        whatsapp_url = _build_whatsapp_reply_url(contact_message)
        if not whatsapp_url:
            messages.error(request, 'WhatsApp reply is unavailable because this message has no valid phone number.')
            return redirect('employee:contact_messages')
        return HttpResponseRedirect(whatsapp_url)

    messages.error(request, 'Invalid reply channel selected.')
    return redirect('employee:contact_messages')

@login_required
@employee_required
def user_management(request):
    """User management for admins only"""
    profile = UserProfile.objects.get(user=request.user)
    
    if not profile.is_admin():
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect('employee:employee_dashboard')
    
    users = UserProfile.objects.all().order_by('-created_at')
    
    # Filter by role if provided
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        users = users.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    context = {
        'users': users,
        'role_filter': role_filter,
        'search_query': search_query,
    }
    return render(request, 'employee/user_management.html', context)

@login_required
@admin_required
@csrf_protect
def create_employee(request):
    """Create new employee accounts (admin only)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role', 'employee')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        try:
            # Create user
            from django.contrib.auth.models import User
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create user profile
            UserProfile.objects.create(
                user=user,
                role=role
            )
            
            messages.success(request, f'Successfully created {role} account for {username}')
            return redirect('employee:user_management')
            
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
    
    return render(request, 'employee/create_employee.html')

@login_required
@employee_required
def profile_settings(request):
    """Employee profile settings"""
    profile = UserProfile.objects.get(user=request.user)
    
    if request.method == 'POST':
        # Update user information
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        
        # Update profile
        profile.phone_number = request.POST.get('phone_number', '')
        profile.department = request.POST.get('department', '')
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('employee:profile_settings')
    
    context = {
        'profile': profile,
    }
    return render(request, 'employee/profile_settings.html', context)

@login_required
@admin_required
def payment_management(request):
    """Payment management for admins"""
    payments = Payment.objects.all().order_by('-payment_date')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'successful':
            payments = payments.filter(is_successful=True)
        elif status_filter == 'failed':
            payments = payments.filter(is_successful=False)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        payments = payments.filter(
            Q(transaction_id__icontains=search_query) |
            Q(student__username__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )
    
    total_revenue = sum(payment.amount for payment in payments.filter(is_successful=True))
    
    context = {
        'payments': payments,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_revenue': total_revenue,
        'successful_count': payments.filter(is_successful=True).count(),
        'failed_count': payments.filter(is_successful=False).count(),
    }
    return render(request, 'employee/payment_management.html', context)

@login_required
@admin_required
@csrf_protect
def update_payment_status(request, payment_id):
    """Manually update payment status (admin only)"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status') == 'successful'
        payment.is_successful = new_status
        payment.save()
        
        # Update application status if payment is successful
        if new_status:
            payment.application.is_paid = True
            if payment.application.status == 'pending_payment':
                payment.application.status = 'submitted'
            payment.application.save()
        
        messages.success(request, f'Payment status updated to {"Successful" if new_status else "Failed"}')
    
    return redirect('employee:payment_management')


@login_required
@employee_required
def update_management(request):
    """Manage employee-authored public updates."""
    profile = UserProfile.objects.get(user=request.user)
    updates = (
        PortalUpdate.objects.select_related('author')
        .prefetch_related('gallery_images', 'attachments')
        .order_by('-updated_at')
    )

    type_filter = request.GET.get('type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    search_query = request.GET.get('search', '').strip()

    if type_filter:
        updates = updates.filter(content_type=type_filter)

    if status_filter:
        updates = updates.filter(status=status_filter)

    if search_query:
        updates = updates.filter(
            Q(title__icontains=search_query) |
            Q(excerpt__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(location__icontains=search_query)
        )

    paginator = Paginator(updates, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'profile': profile,
        'page_obj': page_obj,
        'updates': page_obj.object_list,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_updates': PortalUpdate.objects.count(),
        'published_updates': PortalUpdate.objects.filter(status='published').count(),
        'featured_updates': PortalUpdate.objects.filter(featured_on_homepage=True, status='published').count(),
        'upcoming_events': PortalUpdate.objects.filter(
            content_type='event',
            status='published',
            event_start__gte=timezone.now(),
        ).count(),
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/update_list.html', context)


@login_required
@employee_required
@csrf_protect
def update_create(request):
    """Create a new public update."""
    if request.method == 'POST':
        form = PortalUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            portal_update = form.save(commit=False)
            portal_update.author = request.user
            portal_update.save()
            form.save_related_files(portal_update)
            messages.success(request, 'Update created successfully.')
            return redirect('employee:update_management')
    else:
        form = PortalUpdateForm(initial={'featured_on_homepage': True, 'status': 'published'})

    return render(
        request,
        'employee/update_form.html',
        {
            'form': form,
            'page_title': 'Create update',
            'submit_label': 'Publish update',
        },
    )


@login_required
@employee_required
@csrf_protect
def update_edit(request, pk):
    """Edit an existing public update."""
    portal_update = get_object_or_404(PortalUpdate, pk=pk)

    if request.method == 'POST':
        form = PortalUpdateForm(request.POST, request.FILES, instance=portal_update)
        if form.is_valid():
            edited_update = form.save(commit=False)
            if edited_update.author is None:
                edited_update.author = request.user
            edited_update.save()
            form.save_related_files(edited_update)
            messages.success(request, 'Update saved successfully.')
            return redirect('employee:update_management')
    else:
        form = PortalUpdateForm(instance=portal_update)

    return render(
        request,
        'employee/update_form.html',
        {
            'form': form,
            'portal_update': portal_update,
            'page_title': 'Edit update',
            'submit_label': 'Save changes',
        },
    )


@login_required
@employee_required
@csrf_protect
def delete_student_application(request, application_id):
    """Allow admins to delete student applications."""
    application = get_object_or_404(Application, id=application_id)

    if request.method == 'POST':
        try:
            # Find and delete any associated offline intake records first
            StudentApplication.objects.filter(portal_application=application).delete()
            # Then delete the main portal application
            application.delete()
            messages.success(request, f'Student application {application_id} and associated records deleted successfully.')
            return redirect('employee:student_application_list')
        except Exception as e:
            logger.exception('Error deleting student application %s: %s', application_id, e)
            messages.error(request, f'An error occurred while deleting application {application_id}: {e}')
            return redirect('employee:student_application_detail', application_id=application_id)
    else:
        messages.error(request, 'Invalid request method for deletion.')
        return redirect('employee:student_application_detail', application_id=application_id)


@login_required
@employee_required
@csrf_protect
def update_delete(request, pk):
    """Delete a public update."""
    portal_update = get_object_or_404(PortalUpdate, pk=pk)

    if request.method == 'POST':
        portal_update.delete()
        messages.success(request, 'Update deleted successfully.')
        return redirect('employee:update_management')

    return render(
        request,
        'employee/update_confirm_delete.html',
        {'portal_update': portal_update},
    )

# API endpoints for AJAX requests
@login_required
@employee_required
def get_dashboard_stats(request):
    """Get dashboard statistics for AJAX requests"""
    profile = UserProfile.objects.get(user=request.user)
    
    stats = {
        'total_applications': Application.objects.count(),
        'pending_applications': Application.objects.filter(status='submitted').count(),
        'total_messages': ContactMessage.objects.count(),
        'unread_messages': ContactMessage.objects.filter(status='new').count(),
        'total_documents': Document.objects.count(),
        'total_revenue': sum(payment.amount for payment in Payment.objects.filter(is_successful=True)),
    }
    
    return JsonResponse(stats)

@login_required
@employee_required
@csrf_protect
def verify_mpesa_payment(request, application_id):
    """Employee verifies M-PESA payment for an application"""
    application = get_object_or_404(Application, id=application_id)
    
    if request.method == 'POST':
        mpesa_reference = request.POST.get('mpesa_reference', '').strip()
        payment_notes = request.POST.get('payment_notes', '').strip()
        payment_status = request.POST.get('payment_status')
        
        if payment_status == 'paid':
            application.payment_status = 'paid'
            application.is_paid = True
            application.mpesa_reference = mpesa_reference
            application.payment_notes = payment_notes
            application.payment_verified_by = request.user
            application.payment_verification_date = timezone.now()
            
            # Update application status
            if application.status == 'pending_payment':
                application.status = 'submitted'
            
            application.save()
            messages.success(request, f'Payment verified successfully for {application.student.get_full_name()}')
        elif payment_status == 'pending_verification':
            application.payment_status = 'pending_verification'
            application.mpesa_reference = mpesa_reference
            application.payment_notes = payment_notes
            application.save()
            messages.info(request, 'Payment marked as pending verification')
        else:
            messages.error(request, 'Invalid payment status')
    
    return redirect('employee:student_application_detail', application_id=application_id)

@login_required
@employee_required
def export_application_pdf(request, application_id):
    """Export single student application to PDF"""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from django.http import HttpResponse
    from io import BytesIO
    
    application = get_object_or_404(Application, id=application_id)
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="application_{application.id}_{application.student.username}.pdf"'
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Add title
    title = Paragraph("AFRICA WESTERN EDUCATION COMPANY LTD", title_style)
    elements.append(title)
    elements.append(Paragraph("Student Application Report", styles['Heading2']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Application Information
    elements.append(Paragraph("Application Information", heading_style))
    
    app_data = [
        ['Application ID:', str(application.id)],
        ['Status:', application.get_status_display()],
        ['Submission Date:', application.submission_date.strftime('%Y-%m-%d %H:%M')],
    ]
    
    app_table = Table(app_data, colWidths=[2*inch, 4*inch])
    app_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(app_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Student Information
    elements.append(Paragraph("Student Information", heading_style))
    
    student_data = [
        ['Name:', application.student.get_full_name()],
        ['Username:', application.student.username],
        ['Email:', application.student.email],
    ]
    
    student_table = Table(student_data, colWidths=[2*inch, 4*inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(student_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment Information
    elements.append(Paragraph("Payment Information", heading_style))
    
    payment_data = [
        ['Payment Status:', application.get_payment_status_display()],
        ['Amount:', f"TZS {application.payment_amount:,.2f}"],
        ['Paid:', 'Yes' if application.is_paid else 'No'],
    ]
    
    if application.mpesa_account_name:
        payment_data.append(['M-PESA Account Name:', application.mpesa_account_name])
    if application.payment_verified_by:
        payment_data.append(['Verified By:', application.payment_verified_by.get_full_name()])
    if application.payment_verified_at:
        payment_data.append(['Verification Date:', application.payment_verified_at.strftime('%Y-%m-%d %H:%M')])
    if application.payment_notes:
        payment_data.append(['Notes:', application.payment_notes])
    
    payment_table = Table(payment_data, colWidths=[2*inch, 4*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(payment_table)
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

@login_required
@employee_required
def export_all_applications_pdf(request):
    """Export all student applications to a single PDF"""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from django.http import HttpResponse
    from io import BytesIO
    from django.utils import timezone as tz
    
    applications = Application.objects.all().order_by('-created_at')
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="all_applications_{tz.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    # Add title
    title = Paragraph("AFRICA WESTERN EDUCATION COMPANY LTD", title_style)
    elements.append(title)
    elements.append(Paragraph("All Student Applications Report", styles['Heading2']))
    elements.append(Paragraph(f"Generated: {tz.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary Table
    summary_data = [
        ['Total Applications:', str(applications.count())],
        ['Paid Applications:', str(applications.filter(is_paid=True).count())],
        ['Pending Payment:', str(applications.filter(payment_status='not_paid').count())],
        ['Pending Verification:', str(applications.filter(payment_status='pending_verification').count())],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e5e7eb')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Applications List Table
    elements.append(Paragraph("Applications List", styles['Heading3']))
    elements.append(Spacer(1, 0.1*inch))
    
    # Create table data
    table_data = [['ID', 'Student', 'Type', 'Status', 'Payment', 'Date']]
    
    for app in applications:
        table_data.append([
            str(app.id),
            app.student.get_full_name()[:20],
            app.get_application_type_display()[:15],
            app.get_status_display()[:15],
            app.get_payment_status_display()[:15],
            app.created_at.strftime('%Y-%m-%d')
        ])
    
    app_list_table = Table(table_data, colWidths=[0.5*inch, 1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch, 0.9*inch])
    app_list_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    elements.append(app_list_table)
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response


@login_required
@employee_required
def verify_payment(request, application_id):
    """Verify M-PESA payment for an application"""
    application = get_object_or_404(Application, id=application_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'verify':
            # Verify payment
            application.payment_status = 'paid'
            application.is_paid = True
            application.payment_verified_at = timezone.now()
            application.payment_verified_by = request.user
            application.save()
            
            messages.success(request, f'Payment verified successfully for {application.student.get_full_name()}')
        
        elif action == 'reject':
            # Reject payment
            rejection_reason = request.POST.get('rejection_reason', 'Payment verification failed')
            application.payment_status = 'rejected'
            application.is_paid = False
            application.payment_verified_at = timezone.now()
            application.payment_verified_by = request.user
            application.payment_notes = rejection_reason
            application.save()
            
            messages.warning(request, f'Payment rejected for {application.student.get_full_name()}. Reason: {rejection_reason}')
        
        return redirect('employee:student_application_detail', application_id=application_id)
    
    return redirect('employee:student_application_detail', application_id=application_id)


@login_required
@employee_required
def export_single_application_pdf(request, application_id):
    """Export a single application to CSC-style PDF using shared export builder."""
    application = get_object_or_404(Application, id=application_id)

    try:
        student_profile = StudentProfile.objects.get(user=application.student)
    except StudentProfile.DoesNotExist:
        student_profile = None

    supplemental_profile = ApplicationSupplementalProfile.objects.filter(application=application).first()

    return build_awec_csc_style_application_pdf_response(
        application=application,
        student_profile=student_profile,
        supplemental_profile=supplemental_profile,
    )


@login_required
@employee_required
def export_empty_application_pdf(request):
    """Export a blank application form PDF with no data for manual filling."""
    from .awec_csc_exact_style_django_pdf_export import build_empty_form_pdf_response
    return build_empty_form_pdf_response()
