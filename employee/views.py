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
import re
from global_agency.models import ContactMessage, StudentApplication, StudentProfile as GlobalStudentProfile
from student_portal.models import Application, Document, Payment, StudentProfile
from .forms import OfflineStudentIntakeForm, PartnerRegistrationForm, PortalUpdateForm
from .models import PortalUpdate, UserProfile
from .decorators import employee_required, admin_required, partner_required

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
            else:
                # Logout if user cannot access employee portal
                logout(request)
                messages.error(request, "Access denied. Please use the student or partner portal.")
                return redirect('employee:employee_login')
        except UserProfile.DoesNotExist:
            pass
    
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if user can access employee portal
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.can_access_employee_portal():
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.get_full_name()}!")
                    
                    # Redirect admins to admin dashboard if needed
                    if profile.is_admin():
                        return redirect('employee:admin_dashboard')
                    else:
                        return redirect('employee:employee_dashboard')
                elif profile.can_access_partner_portal():
                    messages.error(request, "This login page is for employees. Please use the partner portal instead.")
                else:
                    messages.error(request, "Access denied. This portal is for admin-created employees only. Students should use the student portal.")
            except UserProfile.DoesNotExist:
                messages.error(request, "Access denied. User profile not found. Please contact administrator.")
        else:
            messages.error(request, "Invalid username or password")
    
    return render(request, "employee/login.html")

@login_required
@employee_required
def employee_dashboard(request):
    # Get user profile for role-based access
    profile = UserProfile.objects.get(user=request.user)
    
    # Get data from both global_agency and student_portal
    applications = StudentApplication.objects.all().order_by('-created_at')
    student_applications = Application.objects.all().order_by('-created_at')  # ALL employees see ALL applications
    contact_messages = ContactMessage.objects.all().order_by('-created_at')
    documents = Document.objects.all().order_by('-uploaded_at')[:10]
    updates = (
        PortalUpdate.objects.select_related('author')
        .prefetch_related('gallery_images', 'attachments')
        .order_by('-updated_at')
    )

    # REMOVED: Assignment logic - all employees see all applications

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
        'recent_updates': updates[:4],
        'is_admin': profile.is_admin(),
        'is_regular_employee': profile.is_regular_employee(),
    }
    return render(request, 'employee/dashboard.html', context)

@login_required
@admin_required
def admin_dashboard(request):
    """Admin-only dashboard with advanced features"""
    profile = UserProfile.objects.get(user=request.user)
    
    # Admin-specific data
    total_students = UserProfile.objects.filter(role='student').count()
    total_employees = UserProfile.objects.filter(role='employee').count()
    total_admins = UserProfile.objects.filter(role='admin').count()
    
    # Recent activity
    recent_applications = Application.objects.all().order_by('-created_at')[:5]
    recent_messages = ContactMessage.objects.all().order_by('-created_at')[:5]
    
    # Payment statistics
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
    messages.success(request, "You have been successfully logged out.")
    return redirect("employee:employee_login")

@login_required
@employee_required
def application_detail(request, pk):
    application = get_object_or_404(StudentApplication, pk=pk)
    profile = UserProfile.objects.get(user=request.user)
    
    context = {
        'application': application,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/application_detail.html', context)

@login_required
@employee_required
def student_application_list(request):
    """View all student portal applications"""
    profile = UserProfile.objects.get(user=request.user)
    
    # ALL employees see ALL applications (removed admin/employee distinction)
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
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        applications_qs = applications_qs.filter(status=status_filter)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        applications_qs = applications_qs.filter(
            Q(student__username__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(university_name__icontains=search_query) |
            Q(course__icontains=search_query) |
            Q(country__icontains=search_query)
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
    """View detailed student portal application"""
    profile = UserProfile.objects.get(user=request.user)
    
    # ALL employees can see ANY application
    application = get_object_or_404(Application, id=application_id)

    partner_intake = (
        StudentApplication.objects.select_related('created_by', 'created_by__userprofile')
        .filter(portal_application=application, created_by__isnull=False)
        .order_by('-created_at')
        .first()
    )
    
    documents = Document.objects.filter(student=application.student)
    payments = Payment.objects.filter(application=application)
    
    # Fetch student profile data if it exists
    try:
        student_profile = StudentProfile.objects.get(user=application.student)
    except StudentProfile.DoesNotExist:
        student_profile = None
    
    context = {
        'application': application,
        'student_profile': student_profile,
        'documents': documents,
        'payments': payments,
        'partner_intake': partner_intake,
        'is_admin': profile.is_admin(),
    }
    return render(request, 'employee/student_application_detail.html', context)


def _build_partner_form_sections(form):
    section_specs = [
        {
            'key': 'student_identity',
            'title': 'Student Identity',
            'description': 'Basic profile and contact details for the student.',
            'icon': 'fa-user-graduate',
            'fields': ['full_name', 'gender', 'nationality', 'email', 'phone', 'address'],
        },
        {
            'key': 'family_selector',
            'title': 'Family Contact Mode',
            'description': 'Choose whether parent details are available or guardian-only details should be used.',
            'icon': 'fa-sliders',
            'fields': ['parent_entry_mode'],
        },
        {
            'key': 'parents',
            'title': 'Parent Details',
            'description': 'Enter one or both parents when available.',
            'icon': 'fa-people-roof',
            'fields': [
                'father_name', 'father_phone', 'father_email', 'father_occupation',
                'mother_name', 'mother_phone', 'mother_email', 'mother_occupation',
            ],
        },
        {
            'key': 'guardian',
            'title': 'Guardian Details',
            'description': 'Required when no parent details are available.',
            'icon': 'fa-user-shield',
            'fields': ['emergency_name', 'emergency_relation', 'emergency_gender', 'emergency_occupation', 'emergency_address'],
        },
        {
            'key': 'olevel',
            'title': 'O-Level Background',
            'description': 'Add O-Level school and performance information.',
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
            'key': 'study_preferences',
            'title': 'Study Preferences',
            'description': 'Capture destination countries and programs of interest.',
            'icon': 'fa-compass-drafting',
            'fields': [
                'preferred_country_1', 'preferred_program_1',
                'preferred_country_2', 'preferred_program_2',
                'preferred_country_3', 'preferred_program_3',
                'preferred_country_4', 'preferred_program_4',
            ],
        },
        {
            'key': 'referral',
            'title': 'Referral Information',
            'description': 'Track how the student heard about Africa Western Education.',
            'icon': 'fa-bullhorn',
            'fields': ['heard_about_us', 'heard_about_other'],
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

@login_required
@employee_required
@csrf_protect
def update_student_application_status(request, application_id):
    """Update student portal application status"""
    profile = UserProfile.objects.get(user=request.user)
    
    # ALL employees can update ANY application
    application = get_object_or_404(Application, id=application_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if new_status in dict(Application.APPLICATION_STATUS):
            application.status = new_status
            application.notes = notes
            application.save()
            messages.success(request, f'Application status updated to {application.get_status_display()}')
        else:
            messages.error(request, 'Invalid status selected.')
def _create_or_update_student_portal_records(cleaned_data, created_by, existing_user=None, portal_application=None, reset_password=True):
    def text_value(key):
        return cleaned_data.get(key) or ''

    full_name = (cleaned_data.get('full_name') or '').strip()
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else ''
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
    email = cleaned_data['email']
    default_password = f"{first_name.upper() or 'STUDENT'}12345"

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

    return user, student_profile, portal_application, default_password


@login_required
@employee_required
@csrf_protect
def offline_application_create(request):
    """Capture an offline application on behalf of a student."""
    if request.method == 'POST':
        form = OfflineStudentIntakeForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                offline_application = form.save(commit=False)
                (
                    student_user,
                    _student_profile,
                    portal_application,
                    default_password,
                ) = _create_or_update_student_portal_records(form.cleaned_data, request.user)

                offline_application.student_user = student_user
                offline_application.account_created = True
                offline_application.username = student_user.username
                offline_application.temporary_password = default_password
                offline_application.save()

            messages.success(
                request,
                f'Offline application saved for {student_user.get_full_name() or student_user.username}. '
                f'Login username: {student_user.username} | Default password: {default_password}',
            )
            return redirect('employee:student_application_detail', application_id=portal_application.id)
    else:
        form = OfflineStudentIntakeForm()

    return render(
        request,
        'employee/offline_application_form.html',
        {
            'form': form,
            'page_title': 'Add offline application',
            'submit_label': 'Save student and create account',
        },
    )


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
        login(request, user)
        messages.success(request, 'Your partner account has been activated successfully.')
        return redirect('employee:partner_dashboard')

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
                messages.error(request, 'Access denied. This login is only for verified partners.')
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
        form = OfflineStudentIntakeForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                offline_application = form.save(commit=False)
                (
                    student_user,
                    _student_profile,
                    portal_application,
                    default_password,
                ) = _create_or_update_student_portal_records(form.cleaned_data, request.user)

                offline_application.student_user = student_user
                offline_application.portal_application = portal_application
                offline_application.created_by = request.user
                offline_application.account_created = True
                offline_application.username = student_user.username
                offline_application.temporary_password = default_password
                offline_application.save()

            messages.success(request, f'Student record created for {student_user.get_full_name() or student_user.username}.')
            return redirect('employee:partner_dashboard')
    else:
        form = OfflineStudentIntakeForm()

    return render(
        request,
        'partner/student_form.html',
        {
            'form': form,
            'form_sections': _build_partner_form_sections(form),
            'page_title': 'Add student record',
            'submit_label': 'Save student record',
        },
    )


@login_required
@partner_required
@csrf_protect
def partner_application_edit(request, pk):
    application = get_object_or_404(StudentApplication, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = OfflineStudentIntakeForm(request.POST, instance=application)
        if form.is_valid():
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
                )

                offline_application.student_user = student_user
                offline_application.portal_application = portal_application
                offline_application.created_by = request.user
                offline_application.account_created = True
                offline_application.username = student_user.username
                offline_application.temporary_password = application.temporary_password
                offline_application.save()

            messages.success(request, 'Student record updated successfully.')
            return redirect('employee:partner_dashboard')
    else:
        form = OfflineStudentIntakeForm(instance=application)

    return render(
        request,
        'partner/student_form.html',
        {
            'form': form,
            'form_sections': _build_partner_form_sections(form),
            'page_title': 'Edit student record',
            'submit_label': 'Update student record',
            'application': application,
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


def _build_email_reply_url(contact_message):
    is_consultation = bool((contact_message.destination or '').strip())
    if is_consultation:
        subject = 'Re: Your Consultation Request - Africa Western Education'
    else:
        subject = 'Re: Your Message - Africa Western Education'

    body = f"Dear {contact_message.name},\n\n"
    body += "Thank you for contacting Africa Western Education.\n\n"

    return f"mailto:{contact_message.email}?subject={quote(subject)}&body={quote(body)}"


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
    """Mark message as handled and redirect employee to reply channel."""
    contact_message = get_object_or_404(ContactMessage, id=message_id)

    if request.method != 'POST':
        messages.error(request, 'Invalid request method for reply action.')
        return redirect('employee:contact_messages')

    if not contact_message.handled:
        contact_message.handled = True
        contact_message.save(update_fields=['handled'])

    if channel == 'email':
        return HttpResponseRedirect(_build_email_reply_url(contact_message))

    if channel == 'whatsapp':
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
    """Export a single application to PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from io import BytesIO
    from django.http import HttpResponse
    
    application = get_object_or_404(Application, id=application_id)
    
    # Fetch student profile if it exists
    try:
        student_profile = StudentProfile.objects.get(user=application.student)
    except StudentProfile.DoesNotExist:
        student_profile = None
    
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    filename = f'Application_{application.id}_{application.student.get_full_name().replace(" ", "_")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create the PDF object
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for PDF elements
    elements = []
    
    # Styles
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
    
    # Title
    elements.append(Paragraph("AFRICA WESTERN EDUCATION COMPANY LTD", title_style))
    elements.append(Paragraph("Student Application Details", styles['Heading2']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Application Information
    elements.append(Paragraph("Application Information", heading_style))
    app_data = [
        ['Application ID:', str(application.id)],
        ['Application Type:', application.get_application_type_display()],
        ['Status:', application.get_status_display()],
        ['Submission Date:', application.created_at.strftime('%B %d, %Y at %I:%M %p')],
        ['Last Updated:', application.updated_at.strftime('%B %d, %Y at %I:%M %p')],
    ]
    
    app_table = Table(app_data, colWidths=[2*inch, 4*inch])
    app_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(app_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Student Profile Picture (if available)
    if student_profile and student_profile.profile_picture:
        try:
            # Add profile picture
            img_path = student_profile.profile_picture.path
            img = Image(img_path, width=1.5*inch, height=1.5*inch)
            img.hAlign = 'LEFT'
            elements.append(img)
            elements.append(Spacer(1, 0.2*inch))
        except:
            # If image can't be loaded, continue without it
            pass
    
    # Student Information
    elements.append(Paragraph("Student Information", heading_style))
    student_data = [
        ['Full Name:', application.student.get_full_name()],
        ['Email:', application.student.email],
        ['Username:', application.student.username],
    ]
    
    # Add all StudentProfile fields if profile exists
    if student_profile:
        student_data.extend([
            ['Phone:', student_profile.phone_number or 'N/A'],
            ['Date of Birth:', str(student_profile.date_of_birth) if student_profile.date_of_birth else 'N/A'],
            ['Gender:', student_profile.get_gender_display() if student_profile.gender else 'N/A'],
            ['Nationality:', student_profile.nationality or 'N/A'],
            ['Address:', student_profile.address or 'N/A'],
        ])
    
    student_table = Table(student_data, colWidths=[2*inch, 4*inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(student_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Parents Information (if available)
    if student_profile and (student_profile.father_name or student_profile.mother_name):
        elements.append(Paragraph("Parents/Guardian Information", heading_style))
        parents_data = []
        
        if student_profile.father_name:
            parents_data.extend([
                ['Father Name:', student_profile.father_name],
                ['Father Phone:', student_profile.father_phone or 'N/A'],
                ['Father Email:', student_profile.father_email or 'N/A'],
                ['Father Occupation:', student_profile.father_occupation or 'N/A'],
            ])
        
        if student_profile.mother_name:
            parents_data.extend([
                ['Mother Name:', student_profile.mother_name],
                ['Mother Phone:', student_profile.mother_phone or 'N/A'],
                ['Mother Email:', student_profile.mother_email or 'N/A'],
                ['Mother Occupation:', student_profile.mother_occupation or 'N/A'],
            ])
        
        if parents_data:
            parents_table = Table(parents_data, colWidths=[2*inch, 4*inch])
            parents_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f9ff')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(parents_table)
            elements.append(Spacer(1, 0.3*inch))
    
    # Emergency Contact Information (if available)
    if student_profile and student_profile.emergency_contact:
        elements.append(Paragraph("Emergency Contact Information", heading_style))
        emergency_data = [
            ['Contact Name:', student_profile.emergency_contact],
            ['Relation:', student_profile.emergency_relation or 'N/A'],
            ['Phone/Gender:', f"{student_profile.emergency_occupation or 'N/A'} / {student_profile.get_emergency_gender_display() if student_profile.emergency_gender else 'N/A'}"],
            ['Address:', student_profile.emergency_address or 'N/A'],
        ]
        
        emergency_table = Table(emergency_data, colWidths=[2*inch, 4*inch])
        emergency_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fef3c7')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(emergency_table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Profile Completion Status
    if student_profile:
        elements.append(Paragraph("Profile Completion Status", heading_style))
        completion_data = [
            ['Personal Details:', 'Complete' if student_profile.personal_details_complete else 'Incomplete'],
            ['Parents Details:', 'Complete' if student_profile.parents_details_complete else 'Incomplete'],
            ['Academic Qualifications:', 'Complete' if student_profile.academic_qualifications_complete else 'Incomplete'],
            ['Study Preferences:', 'Complete' if student_profile.study_preferences_complete else 'Incomplete'],
            ['Emergency Contact:', 'Complete' if student_profile.emergency_contact_complete else 'Incomplete'],
            ['Overall Completion:', f"{student_profile.get_completion_percentage()}%"],
        ]
        
        completion_table = Table(completion_data, colWidths=[2*inch, 4*inch])
        completion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecfdf5')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        elements.append(completion_table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Academic Information
    elements.append(Paragraph("Academic & Educational Information", heading_style))
    academic_data = [
        ['University/Institution:', application.university_name or 'N/A'],
        ['Course/Program:', application.course or 'N/A'],
        ['Country:', application.country or 'N/A'],
    ]
    
    # Add comprehensive student profile academic information if available
    if student_profile:
        # O-Level Education Details
        if student_profile.olevel_school or student_profile.olevel_year or student_profile.olevel_gpa:
            academic_data.extend([
                ['O-Level School:', student_profile.olevel_school or 'N/A'],
                ['O-Level Country:', student_profile.olevel_country or 'N/A'],
                ['O-Level Address:', student_profile.olevel_address or 'N/A'],
                ['O-Level Region:', student_profile.olevel_region or 'N/A'],
                ['O-Level Year:', student_profile.olevel_year or 'N/A'],
                ['O-Level Candidate No:', student_profile.olevel_candidate_no or 'N/A'],
                ['O-Level GPA:', student_profile.olevel_gpa or 'N/A'],
            ])
        
        # A-Level Education Details
        if student_profile.alevel_school or student_profile.alevel_year or student_profile.alevel_gpa:
            academic_data.extend([
                ['A-Level School:', student_profile.alevel_school or 'N/A'],
                ['A-Level Country:', student_profile.alevel_country or 'N/A'],
                ['A-Level Address:', student_profile.alevel_address or 'N/A'],
                ['A-Level Region:', student_profile.alevel_region or 'N/A'],
                ['A-Level Year:', student_profile.alevel_year or 'N/A'],
                ['A-Level Candidate No:', student_profile.alevel_candidate_no or 'N/A'],
                ['A-Level GPA:', student_profile.alevel_gpa or 'N/A'],
            ])
        
        # Study Preferences (all 4 options)
        if student_profile.preferred_country_1 or student_profile.preferred_program_1:
            academic_data.extend([
                ['Preferred Country 1:', student_profile.preferred_country_1 or 'N/A'],
                ['Preferred Program 1:', student_profile.preferred_program_1 or 'N/A'],
            ])
        
        if student_profile.preferred_country_2 or student_profile.preferred_program_2:
            academic_data.extend([
                ['Preferred Country 2:', student_profile.preferred_country_2 or 'N/A'],
                ['Preferred Program 2:', student_profile.preferred_program_2 or 'N/A'],
            ])
        
        if student_profile.preferred_country_3 or student_profile.preferred_program_3:
            academic_data.extend([
                ['Preferred Country 3:', student_profile.preferred_country_3 or 'N/A'],
                ['Preferred Program 3:', student_profile.preferred_program_3 or 'N/A'],
            ])
        
        if student_profile.preferred_country_4 or student_profile.preferred_program_4:
            academic_data.extend([
                ['Preferred Country 4:', student_profile.preferred_country_4 or 'N/A'],
                ['Preferred Program 4:', student_profile.preferred_program_4 or 'N/A'],
            ])
        
        # Additional information
        if student_profile.heard_about_us:
            academic_data.append(['Heard About Us:', student_profile.heard_about_us])
        if student_profile.heard_about_other:
            academic_data.append(['Heard About Us (Other):', student_profile.heard_about_other])
    
    academic_table = Table(academic_data, colWidths=[2*inch, 4*inch])
    academic_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(academic_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment Information
    elements.append(Paragraph("Payment Information", heading_style))
    payment_data = [
        ['Payment Status:', application.get_payment_status_display()],
        ['Payment Amount:', f'{application.payment_amount:,.0f} TZS' if application.payment_amount else 'N/A'],
        ['Is Paid:', 'Yes' if application.is_paid else 'No'],
    ]
    
    if application.mpesa_account_name:
        payment_data.append(['M-PESA Account Name:', application.mpesa_account_name])
    
    if application.payment_verified_at:
        payment_data.append(['Verified At:', application.payment_verified_at.strftime('%B %d, %Y at %I:%M %p')])
        if application.payment_verified_by:
            payment_data.append(['Verified By:', application.payment_verified_by.get_full_name()])
    
    payment_table = Table(payment_data, colWidths=[2*inch, 4*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0e7ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Documents
    documents = Document.objects.filter(student=application.student)
    if documents.exists():
        elements.append(Paragraph("Uploaded Documents", heading_style))
        doc_data = [['Document Type', 'Uploaded Date']]
        for document in documents:
            doc_data.append([
                document.get_document_type_display(),
                document.uploaded_at.strftime('%B %d, %Y')
            ])
        
        doc_table = Table(doc_data, colWidths=[3*inch, 3*inch])
        doc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(doc_table)
    
    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
    elements.append(Paragraph("AFRICA WESTERN EDUCATION COMPANY LTD - Confidential", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and write it to the response
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response
