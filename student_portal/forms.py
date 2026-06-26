from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
import logging
from .models import StudentProfile, Application, Document, WorkExperience

logger = logging.getLogger(__name__)
User = get_user_model()

# =============================================================================
# STRICT STUDENT PASSWORD RESET FORM - EXACT EMAIL MATCHING ONLY
# =============================================================================

class StrictStudentPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email', 
            'class': 'reset-input',
            'placeholder': 'Enter your account email address'
        })
    )
    
    def clean_email(self):
        """
        Validate email format only - don't reveal if email exists
        """
        email = self.cleaned_data['email']
        
        # Basic email format validation
        if not email:
            raise forms.ValidationError("Please enter your email address.")
        
        # Email format validation
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Please enter a valid email address.")
        
        return email
    
    def get_users(self, email):
        """
        Get the EXACT user matching this email who is a student
        Returns at most ONE user - the exact account owner
        """
        try:
            # Try to get the exact user - case-insensitive but exact match
            # This ensures we only get users whose email matches exactly
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            
            if not user:
                logger.warning(f"No active user found with email: {email}")
                return User.objects.none()
            
            # Verify this user is actually a student by checking for StudentProfile
            try:
                if hasattr(user, 'studentprofile') and user.studentprofile:
                    logger.info(f"Exact student match found: {user.email} (ID: {user.id})")
                    return [user]  # Return as list for compatibility
                else:
                    logger.warning(f"User exists but is not a student: {email}")
                    return User.objects.none()
            except Exception as e:
                logger.error(f"Error checking student profile for {email}: {str(e)}")
                return User.objects.none()
                
        except Exception as e:
            logger.error(f"Error finding exact user for {email}: {str(e)}")
            return User.objects.none()
    
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        """
        Send email ONLY to the exact email address that was entered
        This ensures the reset link goes to the account owner's email
        """
        try:
            # Add student-specific context to email
            context['user_type'] = 'Student'
            context['portal_name'] = 'Student Portal'
            context['security_notice'] = 'This password reset link is valid only for your account and will expire in 24 hours.'
            
            # Send to the EXACT email that was entered
            super().send_mail(
                subject_template_name, 
                email_template_name, 
                context, 
                from_email, 
                to_email,  # This is the email that was entered in the form
                html_email_template_name
            )
            
            logger.info(f"Password reset email sent to account owner: {to_email}")
            
        except Exception as e:
            logger.error(f"Error sending password reset email to {to_email}: {str(e)}")
            # Re-raise to let Django handle it
            raise
    
    def save(self, domain_override=None,
             subject_template_name=None, email_template_name=None,
             use_https=False, token_generator=None, from_email=None,
             request=None, html_email_template_name=None, extra_email_context=None):
        """
        Send reset email ONLY to the exact email that was entered
        Only proceeds if there's an exact student match
        """
        email = self.cleaned_data["email"]
        
        # Log the attempt
        logger.info(f"Password reset attempt for email: {email}")
        
        # Get the exact matching user (at most one)
        users = self.get_users(email)
        
        if not users:
            # No exact match found - log but don't reveal to user
            logger.warning(f"Password reset blocked - no exact student match for email: {email}")
            return  # Silent fail - user will see generic success message
        
        # Get the single user (the exact account owner)
        user = users[0]
        
        # Generate reset link
        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override
        
        # Create context with user-specific information
        context = {
            'email': email,
            'domain': domain,
            'site_name': site_name,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'user': user,
            'token': token_generator.make_token(user),
            'protocol': 'https' if use_https else 'http',
            'student_name': user.get_full_name() or user.username,
            'expiry_hours': 24,
        }
        
        if extra_email_context:
            context.update(extra_email_context)
        
        # Send to the EXACT email that was entered
        self.send_mail(
            subject_template_name, 
            email_template_name, 
            context, 
            from_email,
            email,  # Send to the entered email (the account owner's email)
            html_email_template_name=html_email_template_name,
        )
        
        logger.info(f"Password reset email successfully queued for account owner: {user.email}")


# =============================================================================
# YOUR EXISTING FORMS (COMPLETELY UNCHANGED)
# =============================================================================

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['phone_number', 'date_of_birth', 'nationality', 'emergency_contact', 'profile_picture']

    def save(self, commit=True):
        instance = super().save(commit=commit)
        sync_helper = getattr(instance, 'sync_normalized_fields', None)
        if sync_helper:
            try:
                sync_helper()
            except Exception:
                pass
        return instance

# Profile Section Forms
class PersonalDetailsForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        label='Full Name',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter your full name'}),
    )

    class Meta:
        model = StudentProfile
        fields = [
            'full_name', 'gender', 'date_of_birth', 'nationality',
            'phone_number', 'place_of_birth',
            'marital_status', 'native_language',
            'city', 'region', 'village', 'ward', 'street',
            'house_no', 'profile_picture',
            'passport_number', 'passport_issue_date', 'passport_expiration_date',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'nationality': forms.TextInput(attrs={'class': 'form-input'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Town / City of birth'}),
            'native_language': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Swahili'}),
            'marital_status': forms.Select(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'city': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'City'}),
            'region': forms.Select(attrs={'class': 'form-input'}),
            'village': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Village'}),
            'ward': forms.Select(attrs={'class': 'form-input'}),
            'street': forms.Select(attrs={'class': 'form-input'}),
            'house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-input'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Passport number'}),
            'passport_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'passport_expiration_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
        labels = {
            'full_name': 'Full Name',
            'date_of_birth': 'Date of Birth',
            'phone_number': 'Phone Number',
            'place_of_birth': 'Place of Birth',
            'marital_status': 'Marital Status',
            'native_language': 'Native Language',
            'profile_picture': 'Profile Picture (Optional)',
            'city': 'City',
            'region': 'Region',
            'village': 'Village',
            'ward': 'Ward',
            'street': 'Street / Mtaa',
            'house_no': 'House / Plot Number',
            'passport_number': 'Passport Number',
            'passport_issue_date': 'Passport Issued Date',
            'passport_expiration_date': 'Passport Expiry Date',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.initial.setdefault('full_name', self.instance.user.get_full_name())
        for fname in ['region', 'ward', 'street']:
            if fname in self.fields:
                self.fields[fname].widget = forms.Select(choices=[('', '--- Select ---')], attrs={'class': 'form-input'})
                self.fields[fname].required = False

    def save(self, commit=True):
        profile = super().save(commit=False)
        full_name = (self.cleaned_data.get('full_name') or '').strip()

        if profile.user_id:
            first_name, _, last_name = full_name.partition(' ')
            profile.user.first_name = first_name
            profile.user.last_name = last_name.strip()

            if commit:
                profile.user.save(update_fields=['first_name', 'last_name'])

        if commit:
            profile.save()

        return profile

class ParentsDetailsForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'father_name', 'father_phone', 'father_email', 'father_occupation',
            'father_country', 'father_region', 'father_district', 'father_ward',
            'father_region_post_code', 'father_district_post_code', 'father_ward_post_code',
            'father_street', 'father_house_no', 'father_place_neighbourhood',
            'father_status', 'father_relationship',
            'mother_name', 'mother_phone', 'mother_email', 'mother_occupation',
            'mother_country', 'mother_region', 'mother_district', 'mother_ward',
            'mother_region_post_code', 'mother_district_post_code', 'mother_ward_post_code',
            'mother_street', 'mother_house_no', 'mother_place_neighbourhood',
            'mother_status', 'mother_relationship',
        ]
        widgets = {
            'father_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': "Father's Full Name"}),
            'father_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'father_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'father@example.com'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
            'father_country': forms.TextInput(attrs={'class': 'form-input'}),
            'father_region': forms.TextInput(attrs={'class': 'form-input'}),
            'father_district': forms.TextInput(attrs={'class': 'form-input'}),
            'father_ward': forms.TextInput(attrs={'class': 'form-input'}),
            'father_region_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region post code'}),
            'father_district_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'District post code'}),
            'father_ward_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ward post code'}),
            'father_street': forms.TextInput(attrs={'class': 'form-input'}),
            'father_house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'father_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'father_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Status'}),
            'father_relationship': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Relationship'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': "Mother's Full Name"}),
            'mother_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'mother_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'mother@example.com'}),
            'mother_occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
            'mother_country': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_region': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_district': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_ward': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_region_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region post code'}),
            'mother_district_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'District post code'}),
            'mother_ward_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ward post code'}),
            'mother_street': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'mother_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'mother_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Status'}),
            'mother_relationship': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Relationship'}),
        }
        labels = {
            'father_name': "Father's Full Name",
            'father_phone': "Father's Phone Number",
            'father_email': "Father's Email Address",
            'father_occupation': "Father's Occupation",
            'father_country': "Father's Country",
            'father_region': "Father's Region",
            'father_district': "Father's District",
            'father_ward': "Father's Ward",
            'father_region_post_code': "Region Post Code",
            'father_district_post_code': "District Post Code",
            'father_ward_post_code': "Ward Post Code",
            'father_street': "Father's Street / Mtaa",
            'father_house_no': "Father's House / Plot Number",
            'father_place_neighbourhood': "Father's Place / Neighbourhood",
            'father_status': "Father's Status",
            'father_relationship': "Father's Relationship",
            'mother_name': "Mother's Full Name",
            'mother_phone': "Mother's Phone Number",
            'mother_email': "Mother's Email Address",
            'mother_occupation': "Mother's Occupation",
            'mother_country': "Mother's Country",
            'mother_region': "Mother's Region",
            'mother_district': "Mother's District",
            'mother_ward': "Mother's Ward",
            'mother_region_post_code': "Region Post Code",
            'mother_district_post_code': "District Post Code",
            'mother_ward_post_code': "Ward Post Code",
            'mother_street': "Mother's Street / Mtaa",
            'mother_house_no': "Mother's House / Plot Number",
            'mother_place_neighbourhood': "Mother's Place / Neighbourhood",
            'mother_status': "Mother's Status",
            'mother_relationship': "Mother's Relationship",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for prefix in ['father_', 'mother_']:
            for fname in ['region', 'district', 'ward', 'street']:
                fn = prefix + fname
                if fn in self.fields:
                    self.fields[fn].widget = forms.Select(choices=[('', '--- Select ---')], attrs={'class': 'form-input'})
                    self.fields[fn].required = False

    def save(self, commit=True):
        instance = super().save(commit=commit)
        sync_helper = getattr(instance, 'sync_normalized_fields', None)
        if sync_helper:
            try:
                sync_helper()
            except Exception:
                pass
        return instance

class AcademicQualificationsForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            # O-Level
            'olevel_school', 'olevel_school_country',
            'olevel_school_region', 'olevel_school_district', 'olevel_school_ward',
            'olevel_school_region_post_code', 'olevel_school_district_post_code', 'olevel_school_ward_post_code',
            'olevel_school_street', 'olevel_school_place_neighbourhood', 'olevel_school_house_no',
            'olevel_start_year', 'olevel_completed_year',
            'olevel_candidate_no', 'olevel_gpa',
            'olevel_school_type', 'olevel_exam_board', 'olevel_certificate_no', 'olevel_remarks',
            # A-Level
            'alevel_school', 'alevel_school_country',
            'alevel_school_region', 'alevel_school_district', 'alevel_school_ward',
            'alevel_school_region_post_code', 'alevel_school_district_post_code', 'alevel_school_ward_post_code',
            'alevel_school_street', 'alevel_school_place_neighbourhood', 'alevel_school_house_no',
            'alevel_start_year', 'alevel_completed_year',
            'alevel_candidate_no', 'alevel_gpa',
            'alevel_school_type', 'alevel_exam_board', 'alevel_certificate_no', 'alevel_remarks',
        ]
        widgets = {
            'olevel_school': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Name'}),
            'olevel_school_country': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_school_region': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_school_district': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_school_ward': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_school_region_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region post code'}),
            'olevel_school_district_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'District post code'}),
            'olevel_school_ward_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ward post code'}),
            'olevel_school_street': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_school_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'olevel_school_house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'olevel_start_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Start year (e.g., 2016)'}),
            'olevel_completed_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Year Completed (e.g., 2020)'}),
            'olevel_candidate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Candidate Number'}),
            'olevel_gpa': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'GPA/Division'}),
            'olevel_school_type': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Type'}),
            'olevel_exam_board': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Exam Board'}),
            'olevel_certificate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Certificate No.'}),
            'olevel_remarks': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Remarks'}),
            'alevel_school': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Name'}),
            'alevel_school_country': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_school_region': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_school_district': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_school_ward': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_school_region_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region post code'}),
            'alevel_school_district_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'District post code'}),
            'alevel_school_ward_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ward post code'}),
            'alevel_school_street': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_school_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'alevel_school_house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'alevel_start_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Start year (e.g., 2020)'}),
            'alevel_completed_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Year Completed (e.g., 2022)'}),
            'alevel_candidate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Candidate Number'}),
            'alevel_gpa': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'GPA/Division/Points'}),
            'alevel_school_type': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Type'}),
            'alevel_exam_board': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Exam Board'}),
            'alevel_certificate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Certificate No.'}),
            'alevel_remarks': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Remarks'}),
        }
        labels = {
            'olevel_school': 'O-Level School Name',
            'olevel_school_country': 'Country',
            'olevel_school_region': 'Region',
            'olevel_school_district': 'District',
            'olevel_school_ward': 'Ward',
            'olevel_school_region_post_code': 'Region Post Code',
            'olevel_school_district_post_code': 'District Post Code',
            'olevel_school_ward_post_code': 'Ward Post Code',
            'olevel_school_street': 'Street',
            'olevel_school_place_neighbourhood': 'Place / Neighbourhood',
            'olevel_school_house_no': 'House / Plot Number',
            'olevel_start_year': 'Start Year',
            'olevel_completed_year': 'Year Completed',
            'olevel_candidate_no': 'Index Number',
            'olevel_gpa': 'GPA/Division',
            'olevel_school_type': 'School Type',
            'olevel_exam_board': 'Exam Board',
            'olevel_certificate_no': 'Certificate No.',
            'olevel_remarks': 'Remarks',
            'alevel_school': 'A-Level School Name',
            'alevel_school_country': 'Country',
            'alevel_school_region': 'Region',
            'alevel_school_district': 'District',
            'alevel_school_ward': 'Ward',
            'alevel_school_region_post_code': 'Region Post Code',
            'alevel_school_district_post_code': 'District Post Code',
            'alevel_school_ward_post_code': 'Ward Post Code',
            'alevel_school_street': 'Street',
            'alevel_school_place_neighbourhood': 'Place / Neighbourhood',
            'alevel_school_house_no': 'House / Plot Number',
            'alevel_start_year': 'Start Year',
            'alevel_completed_year': 'Year Completed',
            'alevel_candidate_no': 'Index Number',
            'alevel_gpa': 'GPA/Division/Points',
            'alevel_school_type': 'School Type',
            'alevel_exam_board': 'Exam Board',
            'alevel_certificate_no': 'Certificate No.',
            'alevel_remarks': 'Remarks',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for prefix in ['olevel_school_', 'alevel_school_']:
            for fname in ['region', 'district', 'ward', 'street']:
                fn = prefix + fname
                if fn in self.fields:
                    self.fields[fn].widget = forms.Select(choices=[('', '--- Select ---')], attrs={'class': 'form-input'})
                    self.fields[fn].required = False

class StudyPreferencesForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'preferred_intake',
            'preferred_country_1', 'preferred_program_1',
            'preferred_country_2', 'preferred_program_2',
            'preferred_country_3', 'preferred_program_3',
        ]
        widgets = {
            'preferred_intake': forms.Select(attrs={'class': 'form-input'}),
            'preferred_country_1': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '1st Choice Country'}),
            'preferred_program_1': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '1st Choice Program'}),
            'preferred_country_2': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '2nd Choice Country'}),
            'preferred_program_2': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '2nd Choice Program'}),
            'preferred_country_3': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '3rd Choice Country'}),
            'preferred_program_3': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '3rd Choice Program'}),
        }
        labels = {
            'preferred_intake': 'Preferred Intake',
            'preferred_country_1': 'First Preference - Country',
            'preferred_program_1': 'First Preference - Program',
            'preferred_country_2': 'Second Preference - Country',
            'preferred_program_2': 'Second Preference - Program',
            'preferred_country_3': 'Third Preference - Country',
            'preferred_program_3': 'Third Preference - Program',
        }

class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'emergency_contact', 'emergency_relation',
            'emergency_occupation', 'emergency_phone', 'emergency_email',
            'emergency_alternative_phone',
            'emergency_country', 'emergency_region', 'emergency_district',
            'emergency_ward', 'emergency_street',
            'emergency_region_post_code', 'emergency_district_post_code', 'emergency_ward_post_code',
            'emergency_place_neighbourhood', 'emergency_house_no',
            'emergency_relationship_status', 'emergency_remarks',
            'heard_about_us', 'heard_about_other',
        ]
        widgets = {
            'emergency_contact': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Emergency Contact Full Name'}),
            'emergency_relation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Father, Mother, Guardian'}),
            'emergency_occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'emergency_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'emergency@example.com'}),
            'emergency_alternative_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Alternative phone'}),
            'emergency_country': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_region': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_district': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_ward': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_street': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'emergency_house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'emergency_region_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region post code'}),
            'emergency_district_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'District post code'}),
            'emergency_ward_post_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ward post code'}),
            'emergency_relationship_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Relationship status'}),
            'emergency_remarks': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Remarks'}),
            'heard_about_us': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'How did you hear about us?'}),
            'heard_about_other': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Please specify if "Other"'}),
        }
        labels = {
            'emergency_contact': 'Emergency Contact Name',
            'emergency_relation': 'Relationship to You',
            'emergency_occupation': 'Emergency Contact Occupation',
            'emergency_phone': 'Phone Number',
            'emergency_email': 'Email Address',
            'emergency_alternative_phone': 'Alternative Phone',
            'emergency_country': 'Country',
            'emergency_region': 'Region',
            'emergency_district': 'District',
            'emergency_ward': 'Ward',
            'emergency_street': 'Street',
            'emergency_region_post_code': 'Region Post Code',
            'emergency_district_post_code': 'District Post Code',
            'emergency_ward_post_code': 'Ward Post Code',
            'emergency_place_neighbourhood': 'Place / Neighbourhood',
            'emergency_house_no': 'House / Plot Number',
            'emergency_relationship_status': 'Relationship Status',
            'emergency_remarks': 'Remarks',
            'heard_about_us': 'How Did You Hear About Us?',
            'heard_about_other': 'Other (Please Specify)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname in ['emergency_region', 'emergency_district', 'emergency_ward', 'emergency_street']:
            if fname in self.fields:
                self.fields[fname].widget = forms.Select(choices=[('', '--- Select ---')], attrs={'class': 'form-input'})
                self.fields[fname].required = False

    def save(self, commit=True):
        instance = super().save(commit=commit)
        sync_helper = getattr(instance, 'sync_normalized_fields', None)
        if sync_helper:
            try:
                sync_helper()
            except Exception:
                pass
        return instance

class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = [
            'company_name', 'position',
            'country', 'region', 'district', 'ward', 'street', 'mtaa',
            'house_no', 'location',
            'start_date', 'end_date', 'currently_working',
            'employment_type', 'supervisor', 'supervisor_contact',
            'description', 'responsibilities', 'achievements', 'remarks',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Company/Organization Name'
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Your Job Title'
            }),
            'country': forms.TextInput(attrs={'class': 'form-input'}),
            'region': forms.TextInput(attrs={'class': 'form-input'}),
            'district': forms.TextInput(attrs={'class': 'form-input'}),
            'ward': forms.TextInput(attrs={'class': 'form-input'}),
            'street': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Street / Mtaa'}),
            'mtaa': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Mtaa name (if different)'}),
            'house_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'House / Plot number'}),
            'location': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'City, Country (legacy)'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
            'currently_working': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-blue-600 rounded',
                'onclick': 'toggleEndDate()'
            }),
            'employment_type': forms.Select(attrs={'class': 'form-input'}, choices=[
                ('', '---------'),
                ('full_time', 'Full-Time'),
                ('part_time', 'Part-Time'),
                ('contract', 'Contract'),
                ('internship', 'Internship'),
                ('volunteer', 'Volunteer'),
                ('self_employed', 'Self-Employed'),
                ('freelance', 'Freelance'),
            ]),
            'supervisor': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Supervisor / Manager name'
            }),
            'supervisor_contact': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Supervisor phone / email'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Brief description of your role and responsibilities...'
            }),
            'responsibilities': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 4,
                'placeholder': '• List your key responsibilities\n• Use bullet points for clarity'
            }),
            'achievements': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Notable achievements, promotions, awards, or impact you made...'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Any additional remarks'
            }),
        }
        labels = {
            'company_name': 'Company/Organization',
            'position': 'Position/Job Title',
            'country': 'Workplace Country',
            'region': 'Region',
            'district': 'District',
            'ward': 'Ward',
            'street': 'Street / Mtaa',
            'mtaa': 'Mtaa Name (if different)',
            'house_no': 'House / Plot Number',
            'location': 'Work Location (legacy)',
            'start_date': 'Start Date',
            'end_date': 'End Date',
            'currently_working': 'I currently work here',
            'employment_type': 'Employment Type',
            'supervisor': 'Supervisor Name',
            'supervisor_contact': 'Supervisor Contact',
            'description': 'Job Description',
            'responsibilities': 'Key Responsibilities',
            'achievements': 'Achievements & Impact',
            'remarks': 'Additional Remarks',
        }
        help_texts = {
            'start_date': 'When did you start this position?',
            'end_date': 'When did you leave this position? (Leave blank if currently working)',
            'responsibilities': 'Use bullet points to list your main duties and responsibilities',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname in ['region', 'district', 'ward', 'street']:
            if fname in self.fields:
                self.fields[fname].widget = forms.Select(choices=[('', '--- Select ---')], attrs={'class': 'form-input'})
                self.fields[fname].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        currently_working = cleaned_data.get('currently_working')
        
        if start_date and end_date and not currently_working:
            if end_date < start_date:
                raise forms.ValidationError("End date cannot be before start date.")
        
        if currently_working:
            cleaned_data['end_date'] = None
        
        return cleaned_data

class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = []

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['document_type', 'file', 'description']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-input'}),
            'file': forms.FileInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional description'}),
        }