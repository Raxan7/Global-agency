from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.db.models import Prefetch
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseRedirect, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone
from urllib.parse import quote
import logging
import re
from global_agency.models import ContactMessage, StudentApplication, StudentProfile as GlobalStudentProfile
from student_portal.models import Application, ApplicationSupplementalProfile, Document, Payment, StudentProfile
from .forms import (
    DOCUMENT_FLAG_FIELD_MAP,
    DOCUMENT_UPLOAD_FIELD_MAP,
    SUPPLEMENTAL_FIELD_NAMES,
    OfflineStudentIntakeForm,
    PartnerRegistrationForm,
    PortalUpdateForm,
)
from .models import PortalUpdate, UserProfile
from .decorators import employee_required, admin_required, partner_required
from .pdf_exports import build_csc_style_application_pdf

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
            | Q(university_name__icontains=search_query)
            | Q(course__icontains=search_query)
            | Q(country__icontains=search_query)
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
):
    def text_value(key):
        return cleaned_data.get(key) or ''

    def persist_field_file(field_file, uploaded_file, fallback_prefix):
        original_name = getattr(uploaded_file, 'name', '') or f'{fallback_prefix}'
        file_name = original_name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        field_file.save(file_name, uploaded_file, save=False)

    full_name = (cleaned_data.get('full_name') or '').strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ''
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
    email = cleaned_data['email']
    default_password = f"{(first_name.upper() or 'STUDENT')}12345"

    if existing_user is not None:
        user = existing_user
        user_created = False
    else:
        user, user_created = User.objects.get_or_create(
            username=email,
            defaults={
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
            },
        )

    user.username = email
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    if reset_password or user_created:
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

    student_profile, _ = StudentProfile.objects.update_or_create(
        user=user,
        defaults={
            'phone_number': text_value('phone'),
            'address': text_value('address'),
            'date_of_birth': cleaned_data.get('date_of_birth'),
            'nationality': text_value('nationality'),
            'gender': text_value('gender'),
            'father_name': text_value('father_name'),
            'father_phone': text_value('father_phone'),
            'father_email': text_value('father_email'),
            'father_occupation': text_value('father_occupation'),
            'mother_name': text_value('mother_name'),
            'mother_phone': text_value('mother_phone'),
            'mother_email': text_value('mother_email'),
            'mother_occupation': text_value('mother_occupation'),
            'olevel_school': text_value('olevel_school'),
            'olevel_country': text_value('olevel_country'),
            'olevel_address': text_value('olevel_address'),
            'olevel_region': text_value('olevel_region'),
            'olevel_year': text_value('olevel_year'),
            'olevel_candidate_no': text_value('olevel_candidate_no'),
            'olevel_gpa': text_value('olevel_gpa'),
            'alevel_school': text_value('alevel_school'),
            'alevel_country': text_value('alevel_country'),
            'alevel_address': text_value('alevel_address'),
            'alevel_region': text_value('alevel_region'),
            'alevel_year': text_value('alevel_year'),
            'alevel_candidate_no': text_value('alevel_candidate_no'),
            'alevel_gpa': text_value('alevel_gpa'),
            'preferred_country_1': text_value('preferred_country_1'),
            'preferred_country_2': text_value('preferred_country_2'),
            'preferred_country_3': text_value('preferred_country_3'),
            'preferred_country_4': text_value('preferred_country_4'),
            'preferred_program_1': text_value('preferred_program_1'),
            'preferred_program_2': text_value('preferred_program_2'),
            'preferred_program_3': text_value('preferred_program_3'),
            'preferred_program_4': text_value('preferred_program_4'),
            'emergency_contact': text_value('emergency_name'),
            'emergency_address': text_value('emergency_address'),
            'emergency_occupation': text_value('emergency_occupation'),
            'emergency_gender': text_value('emergency_gender'),
            'emergency_relation': text_value('emergency_relation'),
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

    uploader_role = getattr(getattr(created_by, 'userprofile', None), 'role', '')
    uploader_label = 'partner' if uploader_role == 'partner' else 'employee'

    portal_defaults = {
        'student': user,
        'application_type': 'university',
        'university_name': '',
        'course': text_value('preferred_program_1'),
        'country': text_value('preferred_country_1'),
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
    if not supplemental_profile.whatsapp_number:
        supplemental_profile.whatsapp_number = text_value('phone')
    if not supplemental_profile.current_address:
        supplemental_profile.current_address = text_value('address')
    if not supplemental_profile.current_country:
        supplemental_profile.current_country = text_value('nationality') or 'Tanzania'
    if not supplemental_profile.serial_number:
        supplemental_profile.serial_number = f'AWECO/Tz/DSM/{portal_application.id:03d}'

    if profile_picture:
        supplemental_profile.has_passport_photo = True

    for field_name, document_type, _label in DOCUMENT_UPLOAD_FIELD_MAP:
        uploaded_document = (uploaded_files or {}).get(field_name)
        if uploaded_document:
            existing_documents = Document.objects.filter(student=user, document_type=document_type).order_by('-uploaded_at')
            existing_document = existing_documents.first()
            if existing_document:
                existing_documents.exclude(pk=existing_document.pk).delete()
                persist_field_file(existing_document.file, uploaded_document, f'documents/{document_type}')
                existing_document.description = f'Uploaded through the {uploader_label} intake workflow.'
                existing_document.is_verified = False
                existing_document.save(update_fields=['file', 'description', 'is_verified'])
            else:
                document = Document(
                    student=user,
                    document_type=document_type,
                    description=f'Uploaded through the {uploader_label} intake workflow.',
                )
                persist_field_file(document.file, uploaded_document, f'documents/{document_type}')
                document.save()
            document_record = existing_document if existing_document else document
            logger.info(
                'Saved document via %s for %s: type=%s name=%s url=%s',
                document_record.file.storage.__class__.__name__,
                email,
                document_type,
                document_record.file.name,
                document_record.file.url,
            )
            supplemental_flag = DOCUMENT_FLAG_FIELD_MAP.get(field_name)
            if supplemental_flag:
                setattr(supplemental_profile, supplemental_flag, True)

    supplemental_profile.save()

    return user, student_profile, portal_application, default_password


@login_required
@employee_required
@csrf_protect
def offline_application_create(request):
    """Capture an offline application on behalf of a student."""
    supplemental_instance = None
    student_profile_instance = None
    existing_documents = []
    if request.method == 'POST':
        form = OfflineStudentIntakeForm(
            request.POST,
            request.FILES,
            supplemental_instance=supplemental_instance,
            student_profile_instance=student_profile_instance,
            existing_documents=existing_documents,
        )
        if form.is_valid():
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
                    )

                    offline_application.student_user = student_user
                    offline_application.portal_application = portal_application
                    offline_application.created_by = request.user
                    offline_application.account_created = True
                    offline_application.username = student_user.username
                    offline_application.temporary_password = default_password
                    offline_application.save()
            except Exception:
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
                request.POST.get('email'),
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
        },
    )


def _build_intake_form_sections(form):
    section_specs = [
        {
            'key': 'personal_details',
            'title': 'Personal Details',
            'description': 'Start with the same core identity details the student portal collects.',
            'icon': 'fa-user-graduate',
            'fields': ['full_name', 'gender', 'date_of_birth', 'nationality', 'email', 'phone', 'address', 'profile_picture_upload'],
        },
        {
            'key': 'family_selector',
            'title': 'Family Setup',
            'description': 'Choose whether you are entering parents or guardian-only details.',
            'icon': 'fa-sliders',
            'fields': ['parent_entry_mode'],
        },
        {
            'key': 'parents',
            'title': 'Parents Details',
            'description': 'Enter one or both parents when they are available.',
            'icon': 'fa-people-roof',
            'fields': [
                'father_name', 'father_phone', 'father_email', 'father_occupation',
                'mother_name', 'mother_phone', 'mother_email', 'mother_occupation',
            ],
        },
        {
            'key': 'guardian',
            'title': 'Emergency / Guardian Details',
            'description': 'This matches the emergency-contact section from the student portal and AWEC form.',
            'icon': 'fa-user-shield',
            'fields': ['emergency_name', 'emergency_relation', 'emergency_gender', 'emergency_occupation', 'emergency_address'],
        },
        {
            'key': 'passport_and_residence',
            'title': 'Passport And Residence',
            'description': 'Fill the AWEC passport and residence details before moving to academic history.',
            'icon': 'fa-passport',
            'fields': [
                'full_name_passport', 'place_of_birth', 'current_region', 'current_city',
                'current_country', 'current_postal_code', 'whatsapp_number',
                'residential_email', 'current_address', 'passport_number',
                'passport_issue_country', 'passport_issue_date',
                'passport_expiration_date', 'has_valid_visa', 'valid_visa_details',
            ],
        },
        {
            'key': 'olevel',
            'title': 'Academic Qualifications',
            'description': 'Follow the student-portal academic flow first, then add any post-secondary history below.',
            'icon': 'fa-school',
            'fields': ['olevel_school', 'olevel_country', 'olevel_address', 'olevel_region', 'olevel_year', 'olevel_candidate_no', 'olevel_gpa'],
        },
        {
            'key': 'alevel',
            'title': 'A-Level Background',
            'description': 'Add A-Level school details when available.',
            'icon': 'fa-building-columns',
            'fields': ['alevel_school', 'alevel_country', 'alevel_address', 'alevel_region', 'alevel_year', 'alevel_candidate_no', 'alevel_gpa'],
        },
        {
            'key': 'post_secondary',
            'title': 'Post-Secondary And English Tests',
            'description': 'Add certificate, diploma, degree, and English-test details from the AWEC form.',
            'icon': 'fa-book-open-reader',
            'fields': [
                'certificate_institution', 'certificate_field_of_study',
                'certificate_year_completed', 'certificate_gpa',
                'diploma_institution', 'diploma_field_of_study',
                'diploma_year_completed', 'diploma_gpa',
                'bachelor_institution', 'bachelor_field_of_study',
                'bachelor_year_completed', 'bachelor_gpa',
                'master_institution', 'master_field_of_study',
                'master_year_completed', 'master_gpa',
                'phd_institution', 'phd_field_of_study',
                'phd_year_completed', 'phd_gpa',
                'professional_qualifications', 'english_test_name',
                'english_test_score', 'english_test_year',
            ],
        },
        {
            'key': 'study_preferences',
            'title': 'Study Preferences',
            'description': 'Capture the preferred countries, programs, intake, and accommodation choices.',
            'icon': 'fa-compass-drafting',
            'fields': [
                'preferred_country_1', 'preferred_program_1',
                'preferred_country_2', 'preferred_program_2',
                'preferred_country_3', 'preferred_program_3',
                'program_level', 'preferred_intake', 'accommodation_preference',
            ],
        },
        {
            'key': 'finance_medical',
            'title': 'Finance, Medical And Referral',
            'description': 'Complete the remaining AWEC sections before uploads.',
            'icon': 'fa-hand-holding-dollar',
            'fields': [
                'education_sponsor', 'estimated_budget_usd', 'scholarship_applied',
                'scholarship_details', 'has_medical_condition',
                'medical_condition_details', 'needs_special_assistance',
                'special_assistance_details', 'heard_about_us', 'heard_about_other',
            ],
        },
        {
            'key': 'student_assets',
            'title': 'Uploads And Declaration',
            'description': 'Finish with the supporting uploads and declaration items that feed the export checklist.',
            'icon': 'fa-file-arrow-up',
            'fields': [
                field_name for field_name, _document_type, _label in DOCUMENT_UPLOAD_FIELD_MAP
            ] + [
                'has_passport_copy', 'has_passport_photo', 'has_academic_certificates',
                'has_academic_transcripts', 'has_english_test_results',
                'has_cv_resume', 'has_personal_statement',
                'has_recommendation_letters', 'has_financial_proof',
                'has_health_insurance', 'has_other_attachments',
                'other_attachments_description', 'declaration_agreed',
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
    if request.method == 'POST':
        form = OfflineStudentIntakeForm(request.POST, request.FILES)
        if form.is_valid():
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
                    )

                    offline_application.student_user = student_user
                    offline_application.portal_application = portal_application
                    offline_application.created_by = request.user
                    offline_application.account_created = True
                    offline_application.username = student_user.username
                    offline_application.temporary_password = default_password
                    offline_application.save()
            except Exception:
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
                request.POST.get('email'),
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

    if request.method == 'POST':
        form = OfflineStudentIntakeForm(
            request.POST,
            request.FILES,
            instance=application,
            supplemental_instance=supplemental_instance,
            student_profile_instance=student_profile_instance,
            existing_documents=existing_documents,
        )
        if form.is_valid():
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

    all_messages = ContactMessage.objects.all().order_by('-created_at')

    # Filter by handled status if provided
    status_filter = request.GET.get('status')
    if status_filter == 'new':
        all_messages = all_messages.filter(handled=False)
    elif status_filter == 'replied':
        all_messages = all_messages.filter(handled=True)

    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        all_messages = all_messages.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(destination__icontains=search_query) |
            Q(message__icontains=search_query)
        )

    consultations = all_messages.exclude(destination__isnull=True).exclude(destination__exact='')
    contact_messages = all_messages.filter(Q(destination__isnull=True) | Q(destination__exact=''))
    
    context = {
        'contact_messages': contact_messages,
        'consultations': consultations,
        'status_filter': status_filter,
        'search_query': search_query,
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
        ['Application Type:', application.get_application_type_display()],
        ['Status:', application.get_status_display()],
        ['Submission Date:', application.submission_date.strftime('%Y-%m-%d %H:%M')],
    ]
    
    if application.university_name:
        app_data.append(['University:', application.university_name])
    if application.course:
        app_data.append(['Course:', application.course])
    if application.country:
        app_data.append(['Country:', application.country])
    
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

    return build_csc_style_application_pdf(
        application=application,
        student_profile=student_profile,
        supplemental_profile=supplemental_profile,
    )
