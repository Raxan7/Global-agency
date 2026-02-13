from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.core.cache import cache
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.utils import timezone
import json
from datetime import datetime
from .models import StudentProfile, Application, Document, Message, Payment, WorkExperience
from .forms import (StudentProfileForm, DocumentForm, ApplicationForm, 
                    PersonalDetailsForm, ParentsDetailsForm, AcademicQualificationsForm,
                    StudyPreferencesForm, EmergencyContactForm, WorkExperienceForm)
from .clickpesa_service import clickpesa_service

# ADD THIS IMPORT
from employee.models import UserProfile

@csrf_protect
def student_login(request):
    # If user is already authenticated, redirect to dashboard
    if request.user.is_authenticated:
        return redirect('student_portal:dashboard')
    
    # Add cache control to prevent back button issues
    response = render(request, 'student_portal/login.html')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        print(f"Login attempt: {username}")
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Block admin users from student portal
            if user.is_staff or user.is_superuser:
                messages.error(request, 'Admin users cannot login to student portal. Please use the admin site.')
                return render(request, 'student_portal/login.html')
            
            print(f"Authentication successful: {user.username}")
            
            # Login the user
            login(request, user)
            
            # Ensure student profile exists
            try:
                StudentProfile.objects.get(user=user)
            except StudentProfile.DoesNotExist:
                try:
                    StudentProfile.objects.create(
                        user=user,
                        phone_number='',
                        address='',
                        nationality='',
                        emergency_contact=''
                    )
                    print("Student profile created")
                except Exception as e:
                    print(f"Profile creation error: {e}")
            
            messages.success(request, 'Login successful!')
            return redirect('student_portal:dashboard')
        else:
            print("Authentication failed")
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'student_portal/login.html')

# ALL OTHER VIEWS
@login_required(login_url='student_portal:login')
def student_dashboard(request):
    """Student dashboard view"""
    # Ensure student profile exists
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    # Get student data
    applications = Application.objects.filter(student=request.user).select_related('student').prefetch_related('payment_set')
    documents = Document.objects.filter(student=request.user)
    unread_messages = Message.objects.filter(student=request.user, is_read=False)
    
    context = {
        'applications': applications,
        'documents_count': documents.count(),
        'unread_messages_count': unread_messages.count(),
        'profile_completion': profile.get_completion_percentage(),
    }
    
    # Add cache control to prevent back button after logout
    response = render(request, 'student_portal/dashboard.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def student_profile(request):
    """Student profile view"""
    # This will automatically create profile if it doesn't exist
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if created:
        messages.info(request, 'Please complete your profile information.')
    
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('student_portal:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudentProfileForm(instance=profile)
    
    # Add cache control
    response = render(request, 'student_portal/profile.html', {'form': form, 'profile': profile})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

# Profile Section Views
@login_required
def personal_details(request):
    """Personal details form view"""
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = PersonalDetailsForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Personal details saved successfully!')
            return redirect('student_portal:parents_details')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PersonalDetailsForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/personal_details.html', context)

@login_required
def parents_details(request):
    """Parents details form view"""
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ParentsDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Parents details saved successfully!')
            return redirect('student_portal:academic_qualifications')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ParentsDetailsForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/parents_details.html', context)

@login_required
def academic_qualifications(request):
    """Academic qualifications form view"""
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = AcademicQualificationsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Academic qualifications saved successfully!')
            return redirect('student_portal:study_preferences')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AcademicQualificationsForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/academic_qualifications.html', context)

@login_required
def study_preferences(request):
    """Study preferences form view"""
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = StudyPreferencesForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Study preferences saved successfully!')
            return redirect('student_portal:emergency_contact')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StudyPreferencesForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/study_preferences.html', context)

@login_required
def emergency_contact(request):
    """Emergency contact form view"""
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = EmergencyContactForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Emergency contact information saved successfully! Your profile is now complete.')
            return redirect('student_portal:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EmergencyContactForm(instance=profile)
    
    context = {
        'form': form,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/emergency_contact.html', context)


# ============ WORK EXPERIENCE VIEWS ============

@login_required
def work_experience_list(request):
    """Display list of work experiences"""
    profile = get_object_or_404(StudentProfile, user=request.user)
    work_experiences = profile.work_experiences.all()
    
    # Calculate total experience
    total_months = 0
    for exp in work_experiences:
        if exp.start_date:
            end = exp.end_date
            if exp.currently_working:
                end = timezone.now().date()
            if end:
                months = (end.year - exp.start_date.year) * 12 + end.month - exp.start_date.month
                total_months += months
    
    total_years = total_months // 12
    remaining_months = total_months % 12
    
    if total_years > 0 and remaining_months > 0:
        total_experience = f"{total_years} year{'s' if total_years > 1 else ''} {remaining_months} month{'s' if remaining_months > 1 else ''}"
    elif total_years > 0:
        total_experience = f"{total_years} year{'s' if total_years > 1 else ''}"
    elif remaining_months > 0:
        total_experience = f"{remaining_months} month{'s' if remaining_months > 1 else ''}"
    else:
        total_experience = "No experience added"
    
    context = {
        'work_experiences': work_experiences,
        'total_experience': total_experience,
        'total_years': total_years,
        'total_months': remaining_months,
        'profile_completion': profile.get_completion_percentage(),
    }
    
    response = render(request, 'student_portal/work_experience.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def work_experience_add(request):
    """Add new work experience"""
    profile = get_object_or_404(StudentProfile, user=request.user)
    
    if request.method == 'POST':
        form = WorkExperienceForm(request.POST)
        if form.is_valid():
            work_exp = form.save(commit=False)
            work_exp.student = profile
            work_exp.save()
            messages.success(request, 'Work experience added successfully!')
            return redirect('student_portal:work_experience')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = WorkExperienceForm()
    
    context = {
        'form': form,
        'title': 'Add Work Experience',
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/work_experience_form.html', context)

@login_required
def work_experience_edit(request, pk):
    """Edit work experience"""
    profile = get_object_or_404(StudentProfile, user=request.user)
    work_exp = get_object_or_404(WorkExperience, pk=pk, student=profile)
    
    if request.method == 'POST':
        form = WorkExperienceForm(request.POST, instance=work_exp)
        if form.is_valid():
            form.save()
            messages.success(request, 'Work experience updated successfully!')
            return redirect('student_portal:work_experience')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = WorkExperienceForm(instance=work_exp)
    
    context = {
        'form': form,
        'title': 'Edit Work Experience',
        'work_exp': work_exp,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/work_experience_form.html', context)

@login_required
def work_experience_delete(request, pk):
    """Delete work experience"""
    profile = get_object_or_404(StudentProfile, user=request.user)
    work_exp = get_object_or_404(WorkExperience, pk=pk, student=profile)
    
    if request.method == 'POST':
        work_exp.delete()
        messages.success(request, 'Work experience deleted successfully!')
        return redirect('student_portal:work_experience')
    
    context = {
        'work_exp': work_exp,
        'profile_completion': profile.get_completion_percentage(),
    }
    return render(request, 'student_portal/work_experience_confirm_delete.html', context)


# ============ END WORK EXPERIENCE VIEWS ============


@login_required
def applications(request):
    """Applications list view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    applications_list = Application.objects.filter(student=request.user).order_by('-created_at')
    
    # Add cache control
    response = render(request, 'student_portal/applications.html', {'applications': applications_list})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def application_detail(request, application_id):
    """Application detail view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    application = get_object_or_404(Application, id=application_id, student=request.user)
    
    # Add cache control
    response = render(request, 'student_portal/application_detail.html', {'application': application})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
@csrf_protect
def create_application(request):
    """Create application view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            try:
                application = form.save(commit=False)
                application.student = request.user
                application.status = 'pending_payment'
                application.payment_amount = 5000  # Set payment amount
                application.save()
            
                return redirect('student_portal:payment', application_id=application.id)
                
            except Exception as e:
                messages.error(request, f'Error creating application: {str(e)}')
        else:
            # Form is invalid - display errors
            error_messages = []
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        error_messages.append(error)
                    else:
                        field_name = form.fields[field].label if field in form.fields else field
                        error_messages.append(f"{field_name}: {error}")
            
            if error_messages:
                messages.error(request, 'Please correct the following errors:')
                for error_msg in error_messages:
                    messages.error(request, error_msg)
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        form = ApplicationForm()
    
    # Add cache control
    response = render(request, 'student_portal/create_application.html', {'form': form})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
@csrf_protect
def payment_page(request, application_id):
    """M-PESA Manual Payment Instructions"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    application = get_object_or_404(Application, id=application_id, student=request.user)
    
    # Check if application is already paid
    if application.is_paid and application.payment_status == 'paid':
        messages.info(request, 'This application has already been paid and verified.')
        return redirect('student_portal:application_detail', application_id=application.id)
    
    if request.method == 'POST':
        # Student provides the name on their M-PESA account
        mpesa_account_name = request.POST.get('mpesa_account_name', '').strip()
        
        if mpesa_account_name:
            application.mpesa_account_name = mpesa_account_name
            application.payment_status = 'pending_verification'
            application.save()
            messages.success(request, 'Payment details submitted successfully. Our team will verify your payment shortly.')
            return redirect('student_portal:application_detail', application_id=application.id)
        else:
            messages.error(request, 'Please provide the name on your M-PESA account.')
    
    # M-PESA payment details
    mpesa_number = "350361561"
    mpesa_name = "AFRICA WEST EDUCATION COMPANY LIMITED"
    
    context = {
        'application': application,
        'payment_amount': application.payment_amount,
        'mpesa_number': mpesa_number,
        'mpesa_name': mpesa_name,
        'payment_status': application.payment_status,
        'currency': 'TZS'
    }
    
    # Add cache control
    response = render(request, 'student_portal/mpesa_payment.html', context)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def make_payment(request, application_id):
    """Enhanced payment retry functionality"""
    application = get_object_or_404(Application, id=application_id, student=request.user)
    
    # Check if application is already paid
    if application.is_paid:
        messages.success(request, 'This application has already been paid for.')
        return redirect('student_portal:application_detail', application_id=application.id)
    
    # Check for existing payments (failed or pending)
    existing_payments = Payment.objects.filter(
        application=application
    ).order_by('-payment_date')
    
    pending_payment = existing_payments.filter(
        status__in=['pending', 'processing']
    ).first()
    
    failed_payments = existing_payments.filter(
        status='failed'
    )
    
    if request.method == 'POST':
        # Cancel any pending payments before creating a new one
        if pending_payment:
            pending_payment.status = 'failed'
            pending_payment.error_message = 'Cancelled by user for retry'
            pending_payment.save()
        
        # Redirect to payment page to process the new payment
        return redirect('student_portal:payment', application_id=application.id)
    
    context = {
        'application': application,
        'pending_payment': pending_payment,
        'failed_payments': failed_payments,
        'payment_amount': application.payment_amount,
        'currency': settings.CURRENCY,
    }
    
    return render(request, 'student_portal/make_payment.html', context)

# ALL PAYMENT PROCESSING FUNCTIONS REMAIN THE SAME AS BEFORE
def process_clickpesa_mobile_payment(request, application, phone_number):
    """Process mobile money payment through ClickPesa"""
    try:
        # Normalize phone number (ensure it starts with country code without +)
        phone_number = phone_number.strip().replace('+', '').replace(' ', '')
        if phone_number.startswith('0'):
            phone_number = '255' + phone_number[1:]  # Tanzania country code
        
        # Generate unique order reference (alphanumeric like Node.js script)
        order_reference = clickpesa_service.generate_order_reference(application.id)
        
        # Step 1: Preview the payment
        success, preview_data, error_msg = clickpesa_service.preview_ussd_push(
            amount=float(application.payment_amount),
            phone_number=phone_number,
            order_reference=order_reference,
            currency=settings.CURRENCY
        )
        
        if not success:
            messages.error(request, f'Payment preview failed: {error_msg}')
            return redirect('student_portal:payment', application_id=application.id)
        
        # Check if payment channels are available
        active_methods = preview_data.get('activeMethods', [])
        if not active_methods or not any(m.get('status') == 'AVAILABLE' for m in active_methods):
            messages.error(request, 'No payment channels available at the moment. Please try again later.')
            return redirect('student_portal:payment', application_id=application.id)
        
        # Create payment record
        payment = Payment.objects.create(
            student=request.user,
            application=application,
            amount=application.payment_amount,
            currency=settings.CURRENCY,
            payment_method='mobile_money',
            payment_gateway='clickpesa',
            phone_number=phone_number,
            order_reference=order_reference,
            status='pending'
        )
        
        # Step 2: Initiate USSD push
        success, init_data, error_msg = clickpesa_service.initiate_ussd_push(
            amount=float(application.payment_amount),
            phone_number=phone_number,
            order_reference=order_reference,
            currency=settings.CURRENCY
        )
        
        if not success:
            payment.status = 'failed'
            payment.error_message = error_msg
            payment.save()
            messages.error(request, f'Payment initiation failed: {error_msg}')
            return redirect('student_portal:payment', application_id=application.id)
        
        # Update payment with ClickPesa response
        payment.transaction_id = init_data.get('id', '')
        payment.channel = init_data.get('channel', '')
        payment.status = init_data.get('status', 'processing').lower()
        payment.clickpesa_response = init_data
        payment.save()
        
        messages.success(
            request, 
            f'Payment request sent! Please check your phone ({phone_number}) and enter your PIN to complete the payment.'
        )
        
        # Redirect to payment verification page
        return redirect('student_portal:payment_verification', payment_id=payment.id)
        
    except Exception as e:
        messages.error(request, f'Mobile money payment failed: {str(e)}')
        return redirect('student_portal:payment', application_id=application.id)

def process_clickpesa_card_payment(request, application):
    """Process card payment through ClickPesa"""
    try:
        # Generate unique order reference
        order_reference = f"APP{application.id}_{int(datetime.now().timestamp())}"
        
        # Get customer details
        student_profile = StudentProfile.objects.get(user=request.user)
        customer_email = request.user.email or f"{request.user.username}@example.com"
        customer_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
        customer_phone = student_profile.phone_number if hasattr(student_profile, 'phone_number') else ""
        
        # Step 1: Preview card payment
        success, preview_data, error_msg = clickpesa_service.preview_card_payment(
            amount=float(application.payment_amount),
            order_reference=order_reference,
            currency="USD"  # Card payments use USD
        )
        
        if not success:
            messages.error(request, f'Card payment preview failed: {error_msg}')
            return redirect('student_portal:payment', application_id=application.id)
        
        # Create payment record
        payment = Payment.objects.create(
            student=request.user,
            application=application,
            amount=application.payment_amount,
            currency="USD",
            payment_method='card',
            payment_gateway='clickpesa',
            order_reference=order_reference,
            status='pending'
        )
        
        # Step 2: Initiate card payment
        success, init_data, error_msg = clickpesa_service.initiate_card_payment(
            amount=float(application.payment_amount),
            order_reference=order_reference,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_phone=customer_phone,
            currency="USD"
        )
        
        if not success:
            payment.status = 'failed'
            payment.error_message = error_msg
            payment.save()
            messages.error(request, f'Card payment initiation failed: {error_msg}')
            return redirect('student_portal:payment', application_id=application.id)
        
        # Get payment link
        card_payment_link = init_data.get('cardPaymentLink', '')
        if not card_payment_link:
            payment.status = 'failed'
            payment.error_message = 'No payment link received'
            payment.save()
            messages.error(request, 'Failed to generate card payment link')
            return redirect('student_portal:payment', application_id=application.id)
        
        # Update payment with ClickPesa response
        payment.clickpesa_response = init_data
        payment.status = 'processing'
        payment.save()
        
        # Redirect to ClickPesa hosted payment page
        messages.info(request, 'Redirecting to secure card payment page...')
        return redirect(card_payment_link)
        
    except Exception as e:
        messages.error(request, f'Card payment failed: {str(e)}')
        return redirect('student_portal:payment', application_id=application.id)

def process_mobile_money_payment(request, application, phone_number, provider):
    """Process mobile money payment (Legacy/Dummy - for fallback)"""
    try:
        # Generate unique transaction ID
        transaction_id = f"MM{application.id}{int(datetime.now().timestamp())}"
        
        # Create pending payment record
        payment = Payment.objects.create(
            student=request.user,
            application=application,
            amount=application.payment_amount,
            payment_method='mobile_money',
            mobile_provider=provider,
            phone_number=phone_number,
            transaction_id=transaction_id,
            is_successful=False,
            status='pending'
        )
        
        # Simulate payment processing (replace with actual mobile money API integration)
        import time
        time.sleep(2)  # Simulate API call
        
        # For demo purposes, we'll simulate a successful payment
        payment.is_successful = True
        payment.status = 'completed'
        payment.save()
        
        # Update application status
        application.is_paid = True
        application.status = 'submitted'
        application.save()
        
        # Send success message based on provider
        provider_names = {
            'mpesa': 'M-Pesa',
            'tigo_pesa': 'Tigo Pesa', 
            'airtel_money': 'Airtel Money',
            'halopesa': 'HaloPesa'
        }
        
        messages.success(
            request, 
            f'Payment of TZS {application.payment_amount:,} successful via {provider_names.get(provider, "mobile money")}! Your application has been submitted.'
        )
        
        return redirect('student_portal:application_detail', application_id=application.id)
        
    except Exception as e:
        messages.error(request, f'Mobile money payment failed: {str(e)}')
        return redirect('student_portal:payment', application_id=application.id)

def process_bank_transfer(request, application, bank_name, account_number, account_name):
    """Process bank transfer payment"""
    try:
        transaction_id = f"BT{application.id}{int(datetime.now().timestamp())}"
        
        payment = Payment.objects.create(
            student=request.user,
            application=application,
            amount=application.payment_amount,
            payment_method='bank_transfer',
            bank_name=bank_name,
            account_number=account_number,
            account_name=account_name,
            transaction_id=transaction_id,
            is_successful=True,
            status='completed'
        )
        
        application.is_paid = True
        application.status = 'submitted'
        application.save()
        
        messages.success(request, f'Bank transfer payment of TZS {application.payment_amount:,} completed successfully! Your application has been submitted.')
        return redirect('student_portal:application_detail', application_id=application.id)
        
    except Exception as e:
        messages.error(request, f'Bank transfer failed: {str(e)}')
        return redirect('student_portal:payment', application_id=application.id)

def process_card_payment(request, application, card_number, card_holder, expiry_date, cvv):
    """Process card payment"""
    try:
        # Basic card validation
        if len(card_number.replace(' ', '')) < 13:
            messages.error(request, 'Invalid card number')
            return redirect('student_portal:payment', application_id=application.id)
        
        if len(cvv) not in [3, 4]:
            messages.error(request, 'Invalid CVV')
            return redirect('student_portal:payment', application_id=application.id)
        
        card_last_four = card_number.replace(' ', '')[-4:]
        
        transaction_id = f"CD{application.id}{int(datetime.now().timestamp())}"
        
        payment = Payment.objects.create(
            student=request.user,
            application=application,
            amount=application.payment_amount,
            payment_method='card',
            card_last_four=card_last_four,
            card_holder=card_holder,
            transaction_id=transaction_id,
            is_successful=True,
            status='completed'
        )
        
        application.is_paid = True
        application.status = 'submitted'
        application.save()
        
        messages.success(request, f'Card payment of TZS {application.payment_amount:,} completed successfully! Your application has been submitted.')
        return redirect('student_portal:application_detail', application_id=application.id)
        
    except Exception as e:
        messages.error(request, f'Card payment failed: {str(e)}')
        return redirect('student_portal:payment', application_id=application.id)

@login_required
def payment_verification(request, payment_id):
    """Page to verify payment status"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    payment = get_object_or_404(Payment, id=payment_id, student=request.user)
    
    # Auto-check status if payment is pending and using ClickPesa
    if payment.is_pending() and payment.payment_gateway == 'clickpesa':
        success, status_data, error_msg = clickpesa_service.check_payment_status(payment.order_reference)
        
        if success and status_data:
            # Update payment status from ClickPesa response
            # status_data is a list, get the first item
            if isinstance(status_data, list) and len(status_data) > 0:
                payment_info = status_data[0]
                
                clickpesa_status = payment_info.get('status', '').lower()
                payment.status = clickpesa_status
                payment.transaction_id = payment_info.get('id', payment.transaction_id)
                payment.payment_reference = payment_info.get('paymentReference', '')
                payment.message = payment_info.get('message', '')
                payment.clickpesa_response = payment_info
                
                if clickpesa_status in ['success', 'settled']:
                    payment.is_successful = True
                    payment.application.is_paid = True
                    payment.application.status = 'submitted'
                    payment.application.save()
                    messages.success(request, 'Payment verified successfully!')
                elif clickpesa_status == 'failed':
                    payment.is_successful = False
                    messages.error(request, f'Payment failed: {payment.message}')
                else:
                    messages.info(request, 'Payment is still being processed. Please wait...')
                
                payment.save()
    
    if request.method == 'POST':
        # Manual check payment status
        if payment.payment_gateway == 'clickpesa':
            success, status_data, error_msg = clickpesa_service.check_payment_status(payment.order_reference)
            
            if success and status_data:
                if isinstance(status_data, list) and len(status_data) > 0:
                    payment_info = status_data[0]
                    clickpesa_status = payment_info.get('status', '').lower()
                    
                    payment.status = clickpesa_status
                    payment.transaction_id = payment_info.get('id', payment.transaction_id)
                    payment.payment_reference = payment_info.get('paymentReference', '')
                    payment.message = payment_info.get('message', '')
                    payment.clickpesa_response = payment_info
                    
                    if clickpesa_status in ['success', 'settled']:
                        payment.is_successful = True
                        payment.application.is_paid = True
                        payment.application.status = 'submitted'
                        payment.application.save()
                        payment.save()
                        messages.success(request, 'Payment verified successfully!')
                        return redirect('student_portal:applications')
                    elif clickpesa_status == 'failed':
                        payment.is_successful = False
                        payment.save()
                        messages.error(request, f'Payment failed: {payment.message}')
                    else:
                        payment.save()
                        messages.info(request, 'Payment is still being processed. Please wait...')
            else:
                messages.error(request, f'Failed to check payment status: {error_msg}')
        else:
            # Legacy payment verification
            if not payment.is_successful:
                payment.is_successful = True
                payment.status = 'success'
                payment.save()
                
                payment.application.is_paid = True
                payment.application.status = 'submitted'
                payment.application.save()
                
                messages.success(request, 'Payment verified successfully!')
                return redirect('student_portal:applications')
    
    # Add cache control
    response = render(request, 'student_portal/payment_verification.html', {
        'payment': payment,
        'application': payment.application
    })
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def check_payment_status_ajax(request, payment_id):
    """AJAX endpoint to check payment status"""
    try:
        payment = Payment.objects.get(id=payment_id, student=request.user)
        
        if payment.payment_gateway == 'clickpesa' and payment.is_pending():
            success, status_data, error_msg = clickpesa_service.check_payment_status(payment.order_reference)
            
            if success and status_data:
                if isinstance(status_data, list) and len(status_data) > 0:
                    payment_info = status_data[0]
                    clickpesa_status = payment_info.get('status', '').lower()
                    
                    payment.status = clickpesa_status
                    payment.transaction_id = payment_info.get('id', payment.transaction_id)
                    payment.payment_reference = payment_info.get('paymentReference', '')
                    payment.message = payment_info.get('message', '')
                    
                    if clickpesa_status in ['success', 'settled']:
                        payment.is_successful = True
                        payment.application.is_paid = True
                        payment.application.status = 'submitted'
                        payment.application.save()
                    elif clickpesa_status == 'failed':
                        payment.is_successful = False
                    
                    payment.save()
                    
                    return JsonResponse({
                        'status': 'success',
                        'payment_status': payment.status,
                        'is_successful': payment.is_successful,
                        'message': payment.message
                    })
        
        return JsonResponse({
            'status': 'success',
            'payment_status': payment.status,
            'is_successful': payment.is_successful,
            'message': payment.message
        })
        
    except Payment.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Payment not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def check_payment_status(request, payment_id):
    """Utility function to check payment status"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    payment = get_object_or_404(Payment, id=payment_id, student=request.user)
    return JsonResponse({
        'is_successful': payment.is_successful,
        'status': payment.status,
        'transaction_id': payment.transaction_id,
        'amount': payment.amount
    })

@login_required
def documents(request):
    """Documents view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                document = form.save(commit=False)
                document.student = request.user
                document.save()
                messages.success(request, 'Document uploaded successfully!')
                return redirect('student_portal:documents')
            except Exception as e:
                messages.error(request, f'Error uploading document: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DocumentForm()
    
    documents_list = Document.objects.filter(student=request.user).order_by('-uploaded_at')
    
    # Add cache control
    response = render(request, 'student_portal/documents.html', {
        'form': form, 
        'documents': documents_list
    })
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def document_services(request):
    """Document services view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    services = [
        {'type': 'university', 'name': 'University Application', 'description': 'Assistance with university applications'},
        {'type': 'visa', 'name': 'Visa Support', 'description': 'Visa application and processing support'},
        {'type': 'passport', 'name': 'Passport Application', 'description': 'Passport application and renewal'},
        {'type': 'loan', 'name': 'Student Loan Services', 'description': 'Student loan application assistance'},
        {'type': 'tcu', 'name': 'TCU Services', 'description': 'Tanzania Commission for Universities services'},
        {'type': 'flight', 'name': 'Flight Ticket Booking', 'description': 'International flight ticket booking'},
    ]
    
    # Add cache control
    response = render(request, 'student_portal/document_services.html', {'services': services})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def service_form(request, service_type):
    """Service form view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    service_names = {
        'university': 'University Application',
        'visa': 'Visa Support',
        'passport': 'Passport Application',
        'loan': 'Student Loan Services',
        'tcu': 'TCU Services',
        'flight': 'Flight Ticket Booking',
    }
    
    if service_type not in service_names:
        messages.error(request, 'Invalid service type')
        return redirect('student_portal:document_services')
    
    if request.method == 'POST':
        # Process service request
        try:
            # Extract form data based on service type
            service_data = {
                'student': request.user,
                'service_type': service_type,
                'details': json.dumps(request.POST.dict()),
                'status': 'pending'
            }
            
            # Here you would typically save to a ServiceRequest model
            # ServiceRequest.objects.create(**service_data)
            
            messages.success(request, f'{service_names[service_type]} request submitted successfully!')
            return redirect('student_portal:document_services')
            
        except Exception as e:
            messages.error(request, f'Error submitting service request: {str(e)}')
    
    # Add cache control
    response = render(request, 'student_portal/service_form.html', {
        'service_type': service_type,
        'service_name': service_names[service_type]
    })
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def messages_list(request):
    """Messages list view"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    messages_list = Message.objects.filter(student=request.user).order_by('-created_at')
    
    # Mark all as read when user visits messages page
    unread_messages = messages_list.filter(is_read=False)
    if unread_messages.exists():
        unread_messages.update(is_read=True)
    
    # Add cache control
    response = render(request, 'student_portal/messages.html', {'messages_list': messages_list})
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

@login_required
def mark_message_read(request, message_id):
    """Mark message as read"""
    if request.method == 'POST':
        try:
            message = get_object_or_404(Message, id=message_id, student=request.user)
            message.is_read = True
            message.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def student_logout(request):
    """Student logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    # Redirect to login page after logout
    return redirect('student_portal:login')

@login_required
def delete_application(request, application_id):
    """Delete an application"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        try:
            application = get_object_or_404(Application, id=application_id, student=request.user)
            
            # Only allow deletion if not paid
            if not application.is_paid:
                application.delete()
                messages.success(request, 'Application deleted successfully.')
            else:
                messages.error(request, 'Cannot delete paid applications.')
                
        except Exception as e:
            messages.error(request, f'Error deleting application: {str(e)}')
    
    return redirect('student_portal:applications')

@login_required
def delete_document(request, document_id):
    """Delete a document"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        try:
            document = get_object_or_404(Document, id=document_id, student=request.user)
            document.delete()
            messages.success(request, 'Document deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting document: {str(e)}')
    
    return redirect('student_portal:documents')

@login_required
def application_statistics(request):
    """Get application statistics for dashboard"""
    # Ensure student profile exists
    StudentProfile.objects.get_or_create(user=request.user)
    
    applications = Application.objects.filter(student=request.user).select_related('student').prefetch_related('payment_set')
    
    stats = {
        'total': applications.count(),
        'submitted': applications.filter(status='submitted').count(),
        'pending_payment': applications.filter(status='pending_payment').count(),
        'under_review': applications.filter(status='under_review').count(),
        'approved': applications.filter(status='approved').count(),
        'rejected': applications.filter(status='rejected').count(),
    }
    
    return JsonResponse(stats)

# Error handling views
def handler404(request, exception):
    return render(request, 'student_portal/404.html', status=404)

def handler500(request):
    return render(request, 'student_portal/500.html', status=500)

def handler403(request, exception):
    return render(request, 'student_portal/403.html', status=403)

def handler400(request, exception):
    return render(request, 'student_portal/400.html', status=400)

# KEEP ALL CSRF EXEMPT WEBHOOK FUNCTIONS EXACTLY THE SAME
@csrf_exempt
def payment_webhook(request, provider):
    """Webhook endpoint for payment providers (Legacy)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract transaction details based on provider
            transaction_id = None
            status = None
            
            if provider == 'mpesa':
                transaction_id = data.get('TransID')
                status = data.get('ResultCode')
            elif provider == 'tigo_pesa':
                transaction_id = data.get('transaction_id')
                status = data.get('status')
            elif provider == 'airtel_money':
                transaction_id = data.get('id')
                status = data.get('status')
            elif provider == 'halopesa':
                transaction_id = data.get('transactionId')
                status = data.get('status')
            
            if not transaction_id:
                return JsonResponse({'status': 'error', 'message': 'No transaction ID provided'})
            
            # Find and update payment
            try:
                payment = Payment.objects.get(transaction_id=transaction_id)
                
                if status in ['0', 'success', 'completed']:
                    payment.is_successful = True
                    payment.status = 'success'
                    payment.save()
                    
                    payment.application.is_paid = True
                    payment.application.status = 'submitted'
                    payment.application.save()
                    
                else:
                    payment.status = 'failed'
                    payment.save()
                    
                return JsonResponse({'status': 'success'})
                
            except Payment.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Payment not found'})
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'})

@csrf_exempt
def clickpesa_webhook(request):
    """
    Webhook endpoint for ClickPesa payment notifications
    This should be registered in your ClickPesa dashboard
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Log the webhook data
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"ClickPesa webhook received: {data}")
            
            # Extract order reference from webhook data
            order_reference = data.get('orderReference') or data.get('order_reference')
            
            if not order_reference:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'No order reference provided'
                }, status=400)
            
            # Find payment by order reference
            try:
                payment = Payment.objects.get(order_reference=order_reference)
                
                # Extract payment status
                clickpesa_status = data.get('status', '').lower()
                payment.status = clickpesa_status
                payment.transaction_id = data.get('id', payment.transaction_id)
                payment.payment_reference = data.get('paymentReference', '')
                payment.message = data.get('message', '')
                payment.clickpesa_response = data
                
                # Update based on status
                if clickpesa_status in ['success', 'settled']:
                    payment.is_successful = True
                    payment.application.is_paid = True
                    payment.application.status = 'submitted'
                    payment.application.save()
                elif clickpesa_status == 'failed':
                    payment.is_successful = False
                
                payment.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Webhook processed successfully'
                })
                
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for order reference: {order_reference}")
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Payment not found'
                }, status=404)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error', 
                'message': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ClickPesa webhook error: {str(e)}")
            return JsonResponse({
                'status': 'error', 
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error', 
        'message': 'Method not allowed'
    }, status=405)