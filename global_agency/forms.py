from django import forms
from django.contrib.auth.models import User
from .models import ContactMessage, StudentApplication

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
            'olevel_gpa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 3.5 or Division I'
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
            'alevel_gpa': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 3.5 or Division I'
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
        }
