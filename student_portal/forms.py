from django import forms
from .models import StudentProfile, Application, Document, WorkExperience

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['phone_number', 'address', 'date_of_birth', 'nationality', 'emergency_contact', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }

# Profile Section Forms
class PersonalDetailsForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'gender', 'date_of_birth', 'nationality', 
            'phone_number', 'address', 'profile_picture'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'nationality': forms.TextInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-input'}),
        }
        labels = {
            'date_of_birth': 'Date of Birth',
            'phone_number': 'Phone Number',
            'profile_picture': 'Profile Picture (Optional)',
        }

class ParentsDetailsForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'father_name', 'father_phone', 'father_email', 'father_occupation',
            'mother_name', 'mother_phone', 'mother_email', 'mother_occupation',
        ]
        widgets = {
            'father_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Father\'s Full Name'}),
            'father_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'father_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'father@example.com'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Mother\'s Full Name'}),
            'mother_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'mother_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'mother@example.com'}),
            'mother_occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
        }
        labels = {
            'father_name': 'Father\'s Full Name',
            'father_phone': 'Father\'s Phone Number',
            'father_email': 'Father\'s Email Address',
            'father_occupation': 'Father\'s Occupation',
            'mother_name': 'Mother\'s Full Name',
            'mother_phone': 'Mother\'s Phone Number',
            'mother_email': 'Mother\'s Email Address',
            'mother_occupation': 'Mother\'s Occupation',
        }

class AcademicQualificationsForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            # O-Level
            'olevel_school', 'olevel_country', 'olevel_address', 'olevel_region',
            'olevel_year', 'olevel_candidate_no', 'olevel_gpa',
            # A-Level
            'alevel_school', 'alevel_country', 'alevel_address', 'alevel_region',
            'alevel_year', 'alevel_candidate_no', 'alevel_gpa',
        ]
        widgets = {
            # O-Level widgets
            'olevel_school': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Name'}),
            'olevel_country': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Address'}),
            'olevel_region': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region'}),
            'olevel_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Year Completed (e.g., 2020)'}),
            'olevel_candidate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Candidate Number'}),
            'olevel_gpa': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'GPA/Division'}),
            # A-Level widgets
            'alevel_school': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Name'}),
            'alevel_country': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_address': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School Address'}),
            'alevel_region': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Region'}),
            'alevel_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Year Completed (e.g., 2022)'}),
            'alevel_candidate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Candidate Number'}),
            'alevel_gpa': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'GPA/Division/Points'}),
        }
        labels = {
            'olevel_school': 'O-Level School Name',
            'olevel_country': 'Country',
            'olevel_address': 'School Address',
            'olevel_region': 'Region',
            'olevel_year': 'Year Completed',
            'olevel_candidate_no': 'Candidate Number',
            'olevel_gpa': 'GPA/Division',
            'alevel_school': 'A-Level School Name',
            'alevel_country': 'Country',
            'alevel_address': 'School Address',
            'alevel_region': 'Region',
            'alevel_year': 'Year Completed',
            'alevel_candidate_no': 'Candidate Number',
            'alevel_gpa': 'GPA/Division/Points',
        }

class StudyPreferencesForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'preferred_country_1', 'preferred_program_1',
            'preferred_country_2', 'preferred_program_2',
            'preferred_country_3', 'preferred_program_3',
            'preferred_country_4', 'preferred_program_4',
        ]
        widgets = {
            'preferred_country_1': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '1st Choice Country'}),
            'preferred_program_1': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '1st Choice Program'}),
            'preferred_country_2': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '2nd Choice Country'}),
            'preferred_program_2': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '2nd Choice Program'}),
            'preferred_country_3': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '3rd Choice Country'}),
            'preferred_program_3': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '3rd Choice Program'}),
            'preferred_country_4': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '4th Choice Country'}),
            'preferred_program_4': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '4th Choice Program'}),
        }
        labels = {
            'preferred_country_1': 'First Preference - Country',
            'preferred_program_1': 'First Preference - Program',
            'preferred_country_2': 'Second Preference - Country',
            'preferred_program_2': 'Second Preference - Program',
            'preferred_country_3': 'Third Preference - Country',
            'preferred_program_3': 'Third Preference - Program',
            'preferred_country_4': 'Fourth Preference - Country',
            'preferred_program_4': 'Fourth Preference - Program',
        }

class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'emergency_contact', 'emergency_address', 'emergency_occupation',
            'emergency_gender', 'emergency_relation', 'heard_about_us', 'heard_about_other'
        ]
        widgets = {
            'emergency_contact': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Emergency Contact Full Name'}),
            'emergency_address': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Full Address'}),
            'emergency_occupation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Occupation'}),
            'emergency_gender': forms.Select(attrs={'class': 'form-input'}),
            'emergency_relation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Father, Mother, Guardian'}),
            'heard_about_us': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'How did you hear about us?'}),
            'heard_about_other': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Please specify if "Other"'}),
        }
        labels = {
            'emergency_contact': 'Emergency Contact Name',
            'emergency_address': 'Emergency Contact Address',
            'emergency_occupation': 'Emergency Contact Occupation',
            'emergency_gender': 'Emergency Contact Gender',
            'emergency_relation': 'Relationship to You',
            'heard_about_us': 'How Did You Hear About Us?',
            'heard_about_other': 'Other (Please Specify)',
        }


# ADD THIS WORK EXPERIENCE FORM
class WorkExperienceForm(forms.ModelForm):
    class Meta:
        model = WorkExperience
        fields = [
            'company_name', 'position', 'location', 
            'start_date', 'end_date', 'currently_working',
            'description', 'responsibilities', 'achievements'
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
            'location': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'City, Country'
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
        }
        labels = {
            'company_name': 'Company/Organization',
            'position': 'Position/Job Title',
            'location': 'Work Location',
            'start_date': 'Start Date',
            'end_date': 'End Date',
            'currently_working': 'I currently work here',
            'description': 'Job Description',
            'responsibilities': 'Key Responsibilities',
            'achievements': 'Achievements & Impact',
        }
        help_texts = {
            'start_date': 'When did you start this position?',
            'end_date': 'When did you leave this position? (Leave blank if currently working)',
            'responsibilities': 'Use bullet points to list your main duties and responsibilities',
        }
    
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
        fields = ['application_type', 'university_name', 'course', 'country']
        widgets = {
            'application_type': forms.Select(attrs={'class': 'form-input'}),
            'university_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter university name'}),
            'course': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter course/program'}),
            'country': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter country'}),
        }

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['document_type', 'file', 'description']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-input'}),
            'file': forms.FileInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional description'}),
        }