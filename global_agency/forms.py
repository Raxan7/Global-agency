from django import forms
from django.contrib.auth.models import User
from .models import SECONDARY_DIVISION_CHOICES, ContactMessage, StudentApplication

class SimpleRegistrationForm(forms.Form):
    """Simple registration form - just email, password, and name"""
    full_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter your full name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'your.email@example.com'})
    )
    password = forms.CharField(
        min_length=8,
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Create a strong password'})
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm your password'})
    )
    terms_accepted = forms.BooleanField(
        required=True,
        error_messages={'required': 'Please agree to the Terms and Conditions and Privacy Policy.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please login or use a different email.")
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("This email is already registered. Please login or use a different email.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match. Please try again.")
        
        return cleaned_data

class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'destination', 'message']


class StudentApplicationForm(forms.ModelForm):
    privacy_acknowledged = forms.BooleanField(
        required=True,
        error_messages={'required': 'Please confirm that you have read and agreed to the Terms and Privacy Policy.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'declaration_check'}),
    )

    class Meta:
        model = StudentApplication
        fields = '__all__'
        widgets = {
            # Personal Information
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your full name'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control'
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Tanzanian'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'student@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '255712345678'
            }),
            
            # Parents Details
            'father_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Father\'s full name'
            }),
            'father_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '255712345678'
            }),
            'father_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'father@example.com'
            }),
            'father_occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Teacher, Engineer'
            }),
            'mother_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mother\'s full name'
            }),
            'mother_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '255712345678'
            }),
            'mother_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'mother@example.com'
            }),
            'mother_occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Nurse, Business Owner'
            }),
            
            # O-Level
            'olevel_school': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'School name'
            }),
            'olevel_start_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Start year e.g. 2016'
            }),
            'olevel_completed_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Year completed e.g. 2020'
            }),
            'olevel_candidate_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'S1234/2020/0001'
            }),
            'olevel_gpa': forms.Select(choices=SECONDARY_DIVISION_CHOICES, attrs={
                'class': 'form-control',
            }),
            'olevel_school_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'School type'
            }),
            'olevel_exam_board': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exam board'
            }),
            'olevel_certificate_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Certificate no.'
            }),
            'olevel_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Remarks'
            }),

            # A-Level
            'alevel_school': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'School name'
            }),
            'alevel_start_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Start year e.g. 2020'
            }),
            'alevel_completed_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Year completed e.g. 2022'
            }),
            'alevel_candidate_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'S1234/2022/0001'
            }),
            'alevel_gpa': forms.Select(choices=SECONDARY_DIVISION_CHOICES, attrs={
                'class': 'form-control',
            }),
            'alevel_school_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'School type'
            }),
            'alevel_exam_board': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Exam board'
            }),
            'alevel_certificate_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Certificate no.'
            }),
            'alevel_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Remarks'
            }),
            
            # Preferences
            'preferred_country_1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First choice country'
            }),
            'preferred_country_2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Second choice country'
            }),
            'preferred_country_3': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Third choice country'
            }),
            'preferred_program_1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First choice program'
            }),
            'preferred_program_2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Second choice program'
            }),
            'preferred_program_3': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Third choice program'
            }),
            
            # Emergency Contact
            'emergency_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Emergency contact name'
            }),
            'emergency_relation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Uncle, Aunt, Guardian'
            }),
            'emergency_occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Doctor, Teacher'
            }),
            'emergency_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number'
            }),
            'emergency_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address'
            }),
            'emergency_alternative_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Alternative phone'
            }),
            'emergency_relationship_status': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Relationship status'
            }),
            'emergency_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Remarks'
            }),
            'heard_about_us': forms.Select(attrs={
                'class': 'form-control'
            }),
            'heard_about_other': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Please specify'
            }),

            # Personal Details - additional fields
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Place of birth'
            }),
            'native_language': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Swahili'
            }),
            'marital_status': forms.Select(attrs={
                'class': 'form-control'
            }),

            # Parents Details - additional fields
            'father_place_neighbourhood': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Place/Neighbourhood'
            }),
            'father_status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'father_relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Relationship with applicant'
            }),
            'mother_place_neighbourhood': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Place/Neighbourhood'
            }),
            'mother_status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'mother_relationship': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Relationship with applicant'
            }),

            # Study Preferences
            'preferred_intake': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., September 2026'
            }),

            # Declaration
            'declaration_applicant_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name of applicant'
            }),
            'declaration_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'declaration_signature_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Type your full name as signature'
            }),
            'terms_accepted': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),

            # Office Use
            'office_director_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Director's name"
            }),
            'office_approval_status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'office_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason/Notes'
            }),

            # Work Experience 1
            'work1_company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company name'
            }),
            'work1_position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Position held'
            }),
            'work1_worked_from': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'work1_worked_to': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'work1_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'work1_region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Region'
            }),
            'work1_region_post_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Post code'
            }),
            'work1_district': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'District'
            }),
            'work1_district_post_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Post code'
            }),
            'work1_ward': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ward'
            }),
            'work1_ward_post_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Post code'
            }),
            'work1_street': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street'
            }),
            'work1_employment_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Full-time, Part-time'
            }),
            'work1_duties': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your duties'
            }),
            'work1_supervisor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Supervisor's name"
            }),
            'work1_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Remarks'
            }),

            # Work Experience 2
            'work2_company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company name'
            }),
            'work2_position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Position held'
            }),
            'work2_worked_from': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'work2_worked_to': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'work2_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'work2_region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Region'
            }),
            'work2_region_post_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Post code'
            }),
            'work2_district': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'District'
            }),
            'work2_district_post_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Post code'
            }),
            'work2_ward': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ward'
            }),
            'work2_ward_post_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Post code'
            }),
            'work2_street': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Street'
            }),
            'work2_employment_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Full-time, Part-time'
            }),
            'work2_duties': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your duties'
            }),
            'work2_supervisor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Supervisor's name"
            }),
            'work2_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Remarks'
            }),

            # Professional Qualification 1
            'profq1_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Qualification title'
            }),
            'profq1_institution': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Institution name'
            }),
            'profq1_institution_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Institution address'
            }),
            'profq1_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'profq1_period': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 3 years'
            }),
            'profq1_start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'profq1_finished_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'profq1_award_certificate': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Award/Certificate no.'
            }),

            # Professional Qualification 2
            'profq2_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Qualification title'
            }),
            'profq2_institution': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Institution name'
            }),
            'profq2_institution_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Institution address'
            }),
            'profq2_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'profq2_period': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2 years'
            }),
            'profq2_start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'profq2_finished_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'profq2_award_certificate': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Award/Certificate no.'
            }),

            # Professional Qualification 3
            'profq3_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Qualification title'
            }),
            'profq3_institution': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Institution name'
            }),
            'profq3_institution_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Institution address'
            }),
            'profq3_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'profq3_period': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 1 year'
            }),
            'profq3_start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'profq3_finished_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'profq3_award_certificate': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Award/Certificate no.'
            }),
        }
