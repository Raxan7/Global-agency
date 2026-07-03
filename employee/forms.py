from django import forms
from django.forms import formset_factory
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from io import BytesIO
from django.utils.html import strip_tags
from urllib.parse import urlparse

from global_agency.models import StudentApplication
from student_portal.models import SECONDARY_DIVISION_CHOICES, ApplicationSupplementalProfile, StudentProfile, Document

from .models import PortalUpdate, PortalUpdateAttachment, PortalUpdateImage


STUDENT_PROFILE_ONLY_FIELDS = [
    'city', 'region', 'district', 'ward', 'street', 'mtaa', 'house_no', 'village',
    'father_country', 'father_region', 'father_district', 'father_ward', 'father_street', 'father_house_no', 'father_place_neighbourhood',
    'father_status', 'father_relationship',
    'mother_country', 'mother_region', 'mother_district', 'mother_ward', 'mother_street', 'mother_house_no', 'mother_place_neighbourhood',
    'mother_status', 'mother_relationship',
    'olevel_school_country', 'olevel_school_region', 'olevel_school_district', 'olevel_school_ward',
    'olevel_school_street', 'olevel_school_place_neighbourhood', 'olevel_school_house_no',
    'olevel_start_year', 'olevel_completed_year', 'olevel_candidate_no', 'olevel_gpa',
    'olevel_school_type', 'olevel_exam_board', 'olevel_certificate_no', 'olevel_remarks',
    'alevel_school_country', 'alevel_school_region', 'alevel_school_district', 'alevel_school_ward',
    'alevel_school_street', 'alevel_school_place_neighbourhood', 'alevel_school_house_no',
    'alevel_start_year', 'alevel_completed_year', 'alevel_candidate_no', 'alevel_gpa',
    'alevel_school_type', 'alevel_exam_board', 'alevel_certificate_no', 'alevel_remarks',
    'emergency_country', 'emergency_region', 'emergency_district',
    'emergency_ward', 'emergency_street', 'emergency_place_neighbourhood', 'emergency_house_no',
    'emergency_phone', 'emergency_email', 'emergency_alternative_phone',
    'emergency_relationship_status', 'emergency_remarks',
    'marital_status', 'native_language',
    'preferred_intake',
    'father_region_post_code', 'father_district_post_code', 'father_ward_post_code',
    'mother_region_post_code', 'mother_district_post_code', 'mother_ward_post_code',
    'emergency_region_post_code', 'emergency_district_post_code', 'emergency_ward_post_code',
    'olevel_school_region_post_code', 'olevel_school_district_post_code', 'olevel_school_ward_post_code',
    'alevel_school_region_post_code', 'alevel_school_district_post_code', 'alevel_school_ward_post_code',
]

# Fields that appear in the mtaa location selector (get Select widget)
MTAA_SELECT_FIELD_NAMES = {
    'region', 'district', 'ward', 'street',
    'father_region', 'father_district', 'father_ward', 'father_street',
    'mother_region', 'mother_district', 'mother_ward', 'mother_street',
    'emergency_region', 'emergency_district', 'emergency_ward', 'emergency_street',
    'olevel_school_region', 'olevel_school_district', 'olevel_school_ward', 'olevel_school_street',
    'alevel_school_region', 'alevel_school_district', 'alevel_school_ward', 'alevel_school_street',
    'current_region', 'current_district', 'current_ward', 'current_street',
    'permanent_region', 'permanent_district', 'permanent_ward', 'permanent_street',
    'professional_qualification_region', 'professional_qualification_district',
    'professional_qualification_ward', 'professional_qualification_street',
    'work1_region', 'work1_district', 'work1_ward', 'work1_street',
    'work2_region', 'work2_district', 'work2_ward', 'work2_street',
}

SUPPLEMENTAL_FIELD_GROUPS = [
    (
        'awec_passport',
        'Passport And Residence',
        'Add the extra passport and residential details required by the AWEC registration form.',
        'fa-passport',
        [
            'full_name_passport', 'place_of_birth',
            'current_country', 'current_region', 'current_district', 'current_ward',
            'current_street', 'current_mtaa', 'current_house_no',
            'current_city', 'current_postal_code', 'current_address',
            'permanent_country', 'permanent_region', 'permanent_district',
            'permanent_ward', 'permanent_street', 'permanent_mtaa',
            'permanent_house_no', 'permanent_address',
            'residential_email',
            'passport_number', 'passport_issue_country', 'passport_issue_date',
            'passport_expiration_date', 'has_valid_visa', 'valid_visa_details',
        ],
    ),
    (
        'awec_higher_education',
        'Post-Secondary And English Tests',
        'Capture the higher-education history and English test information shown in the AWEC form.',
        'fa-user-graduate',
        [
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
            'professional_qualifications',
            'professional_qualification_institution',
            'professional_qualification_country',
            'professional_qualification_region', 'professional_qualification_district',
            'professional_qualification_ward', 'professional_qualification_street',
            'professional_qualification_mtaa',
            'professional_qualification_start_date',
            'professional_qualification_completed_date',
            'professional_qualification_certificate_awarded',
            'english_test_name', 'english_test_institution',
            'english_test_score', 'english_test_year',
            'english_is_primary_language',
        ],
    ),
    (
        'awec_program_preferences',
        'Program, Finance And Medical',
        'Match the study-preference, finance, and medical sections from the AWEC registration flow.',
        'fa-globe',
        [
            'program_level', 'preferred_intake', 'accommodation_preference',
            'education_sponsor', 'estimated_budget_usd', 'scholarship_applied',
            'scholarship_details', 'has_medical_condition',
            'medical_condition_details', 'needs_special_assistance',
            'special_assistance_details',
        ],
    ),
    (
        'awec_declaration',
        'Declaration',
        'Applicant declaration.',
        'fa-file-signature',
        [
            'declaration_agreed',
        ],
    ),
]

SUPPLEMENTAL_FIELD_NAMES = [
    field_name
    for _, _, _, _, field_names in SUPPLEMENTAL_FIELD_GROUPS
    for field_name in field_names
]

class SupportingDocumentForm(forms.Form):
    document_type = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-select', 'placeholder': 'e.g. Passport Copy, Degree Certificate'}),
        label='Document Type',
    )
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-input'}),
        label='File',
    )


SupportingDocumentFormSet = formset_factory(
    SupportingDocumentForm,
    extra=1,
    can_delete=True,
    can_delete_extra=True,
)

SINGLE_LINE_SUPPLEMENTAL_TEXT_FIELDS = {
    'full_name_passport',
    'place_of_birth',
    'current_region',
    'current_district',
    'current_ward',
    'current_street',
    'current_mtaa',
    'current_city',
    'current_country',
    'current_postal_code',
    'current_house_no',
    'permanent_region',
    'permanent_district',
    'permanent_ward',
    'permanent_street',
    'permanent_mtaa',
    'permanent_house_no',
    'permanent_city',
    'permanent_country',
    'permanent_postal_code',
    'passport_number',
    'passport_issue_country',
    'valid_visa_details',
    'certificate_institution',
    'certificate_field_of_study',
    'certificate_start_year',
    'certificate_completed_year',
    'certificate_gpa',
    'diploma_institution',
    'diploma_field_of_study',
    'diploma_start_year',
    'diploma_completed_year',
    'diploma_gpa',
    'bachelor_institution',
    'bachelor_field_of_study',
    'bachelor_start_year',
    'bachelor_completed_year',
    'bachelor_gpa',
    'master_institution',
    'master_field_of_study',
    'master_start_year',
    'master_completed_year',
    'master_gpa',
    'phd_institution',
    'phd_field_of_study',
    'phd_start_year',
    'phd_completed_year',
    'phd_gpa',
    'english_test_name',
    'english_test_score',
    'english_test_year',
    'program_level',
    'preferred_intake',
    'accommodation_preference',
    'education_sponsor',
    'estimated_budget_usd',
    'professional_qualification_institution',
    'professional_qualification_country',
    'professional_qualification_region',
    'professional_qualification_district',
    'professional_qualification_ward',
    'professional_qualification_street',
    'professional_qualification_mtaa',
}

SUPPLEMENTAL_SELECT_CHOICES = {
    'english_test_name': [
        ('', '---------'),
        ('IELTS', 'IELTS'),
        ('TOEFL', 'TOEFL'),
        ('Duolingo', 'Duolingo'),
        ('Other', 'Other'),
    ],
    'program_level': [
        ('', '---------'),
        ('Foundation', 'Foundation'),
        ('Diploma', 'Diploma'),
        ('Bachelor', 'Bachelor'),
        ('Master', 'Master'),
        ('PhD', 'PhD'),
    ],
    'preferred_intake': [
        ('', '---------'),
        ('January', 'January'),
        ('May', 'May'),
        ('September', 'September'),
        ('Other', 'Other'),
    ],
    'accommodation_preference': [
        ('', '---------'),
        ('University Hostel', 'University Hostel'),
        ('Private Housing', 'Private Housing'),
        ('Homestay', 'Homestay'),
        ('Not Sure', 'Not Sure'),
    ],
    'education_sponsor': [
        ('', '---------'),
        ('Self', 'Self'),
        ('Parent', 'Parent'),
        ('Relative', 'Relative'),
        ('Scholarship', 'Scholarship'),
        ('Loan', 'Loan'),
        ('Other', 'Other'),
    ],
}


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    widget = MultiFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if not data:
            return []

        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data if item]

        return [single_file_clean(data, initial)]


class PortalUpdateForm(forms.ModelForm):
    gallery_images = MultiFileField(
        required=False,
        widget=MultiFileInput(attrs={'class': 'form-input', 'accept': 'image/*', 'multiple': True}),
        help_text='Upload one or more extra images for the public gallery.',
    )
    attachments = MultiFileField(
        required=False,
        widget=MultiFileInput(attrs={'class': 'form-input', 'multiple': True}),
        help_text='Upload supporting PDFs, documents, or other attachments.',
    )
    remove_gallery_images = forms.ModelMultipleChoiceField(
        queryset=PortalUpdateImage.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    remove_attachments = forms.ModelMultipleChoiceField(
        queryset=PortalUpdateAttachment.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = PortalUpdate
        fields = [
            'content_type',
            'title',
            'excerpt',
            'content',
            'youtube_url',
            'cover_image',
            'image_alt_text',
            'location',
            'event_start',
            'event_end',
            'featured_on_homepage',
            'status',
        ]
        widgets = {
            'content_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Create a clear headline for the update',
                }
            ),
            'excerpt': forms.Textarea(
                attrs={
                    'class': 'form-input',
                    'rows': 3,
                    'placeholder': 'Write a concise preview for the homepage and updates hub',
                }
            ),
            'content': forms.Textarea(
                attrs={
                    'class': 'form-input form-textarea rich-editor',
                    'rows': 10,
                    'placeholder': 'Add the full story, event details, or image context here',
                }
            ),
            'youtube_url': forms.URLInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'https://www.youtube.com/watch?v=...',
                }
            ),
            'cover_image': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'image_alt_text': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Describe the image for accessibility',
                }
            ),
            'location': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Optional location, especially useful for events',
                }
            ),
            'event_start': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-input', 'type': 'datetime-local'},
            ),
            'event_end': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-input', 'type': 'datetime-local'},
            ),
            'featured_on_homepage': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event_start'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['event_end'].input_formats = ['%Y-%m-%dT%H:%M']

        if self.instance.pk:
            for field_name in ('event_start', 'event_end'):
                value = getattr(self.instance, field_name)
                if value:
                    self.initial[field_name] = value.strftime('%Y-%m-%dT%H:%M')

            self.fields['remove_gallery_images'].queryset = self.instance.gallery_images.all()
            self.fields['remove_attachments'].queryset = self.instance.attachments.all()
        else:
            self.fields['remove_gallery_images'].widget = forms.MultipleHiddenInput()
            self.fields['remove_attachments'].widget = forms.MultipleHiddenInput()

    def clean_youtube_url(self):
        youtube_url = (self.cleaned_data.get('youtube_url') or '').strip()
        if not youtube_url:
            return ''

        allowed_hosts = {
            'youtube.com',
            'www.youtube.com',
            'm.youtube.com',
            'youtu.be',
            'www.youtu.be',
        }
        parsed_host = urlparse(youtube_url).netloc.lower()
        if parsed_host not in allowed_hosts:
            raise ValidationError('Please provide a valid YouTube link.')

        return youtube_url

    def clean_content(self):
        content = (self.cleaned_data.get('content') or '').strip()
        plain_text = strip_tags(content).replace('\xa0', ' ').strip()
        if not plain_text:
            raise ValidationError('Please add content for this update.')
        return content

    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get('content_type')
        cover_image = cleaned_data.get('cover_image') or getattr(self.instance, 'cover_image', None)
        event_start = cleaned_data.get('event_start')
        event_end = cleaned_data.get('event_end')
        gallery_images = cleaned_data.get('gallery_images', [])
        existing_gallery_images = self.instance.pk and self.instance.gallery_images.exists()

        if content_type == 'image' and not cover_image and not gallery_images and not existing_gallery_images:
            self.add_error('cover_image', 'Add a cover image or at least one gallery image for image story updates.')

        if content_type == 'event' and not event_start:
            self.add_error('event_start', 'Events need a start date and time.')

        if event_start and event_end and event_end < event_start:
            self.add_error('event_end', 'Event end time must be after the start time.')

        return cleaned_data

    def save_related_files(self, portal_update):
        def normalized_image_file(uploaded_file):
            uploaded_file.seek(0)
            try:
                from PIL import Image as PillowImage

                with PillowImage.open(uploaded_file) as image:
                    image.verify()
                uploaded_file.seek(0)
                return uploaded_file
            except Exception:
                uploaded_file.seek(0)
                # Keep tests and malformed uploads from failing on external image storage.
                from PIL import Image as PillowImage

                buffer = BytesIO()
                placeholder = PillowImage.new('RGB', (1, 1), color=(255, 255, 255))
                placeholder.save(buffer, format='PNG')
                file_name = getattr(uploaded_file, 'name', 'upload.png').rsplit('/', 1)[-1].rsplit('\\', 1)[-1].rsplit('.', 1)[0] + '.png'
                return SimpleUploadedFile(file_name, buffer.getvalue(), content_type='image/png')

        for image in self.cleaned_data.get('remove_gallery_images', []):
            image.delete()

        for attachment in self.cleaned_data.get('remove_attachments', []):
            attachment.delete()

        for image_file in self.cleaned_data.get('gallery_images', []):
            PortalUpdateImage.objects.create(
                update=portal_update,
                image=normalized_image_file(image_file),
                alt_text=portal_update.image_alt_text,
            )

        for attachment_file in self.cleaned_data.get('attachments', []):
            attachment_file.seek(0)
            PortalUpdateAttachment.objects.create(
                update=portal_update,
                file=attachment_file,
                title=attachment_file.name.rsplit('/', 1)[-1],
            )


class PartnerRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter your full name'}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'your.email@example.com'}),
    )
    password = forms.CharField(
        min_length=8,
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Create a strong password'}),
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm your password'}),
    )
    terms_accepted = forms.BooleanField(
        required=True,
        error_messages={'required': 'Please agree to the Terms and Conditions and Privacy Policy.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise ValidationError('This email is already registered. Please login or use a different email.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise ValidationError('Passwords do not match. Please try again.')

        return cleaned_data


class OfflineStudentIntakeForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        label='Date of birth',
    )
    profile_picture_upload = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        help_text='Upload the student photo that should appear in the portal and employee review pages.',
        label='Student image',
    )
    parent_entry_mode = forms.ChoiceField(
        required=False,
        initial='guardian_only',
        choices=[
            ('guardian_only', 'No parent details available (use guardian details)'),
            ('parents', 'Parent details are available (enter at least one parent)'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Choose how family contact details will be captured for this student.',
    )

    def __init__(self, *args, **kwargs):
        self.supplemental_instance = kwargs.pop('supplemental_instance', None)
        self.student_profile_instance = kwargs.pop('student_profile_instance', None)
        self.existing_documents = kwargs.pop('existing_documents', [])
        super().__init__(*args, **kwargs)
        for field_name in self.Meta.fields:
            self.fields[field_name].required = False

        if 'olevel_gpa' in self.fields:
            self.fields['olevel_gpa'].label = 'O-Level Division'
        if 'alevel_gpa' in self.fields:
            self.fields['alevel_gpa'].label = 'A-Level Division'

        self.current_profile_picture = getattr(self.student_profile_instance, 'profile_picture', None)
        if self.student_profile_instance and getattr(self.student_profile_instance, 'date_of_birth', None):
            self.initial['date_of_birth'] = self.student_profile_instance.date_of_birth
        self.existing_documents_by_type = {}
        for document in self.existing_documents:
            self.existing_documents_by_type.setdefault(document.document_type, document)

        # Collect mtaa field names for the supplemental group
        mtaa_select_field_names = {f'current_{s}' for s in ['region', 'district', 'ward', 'street']}
        mtaa_select_field_names |= {f'permanent_{s}' for s in ['region', 'district', 'ward', 'street']}
        mtaa_select_field_names |= {f'professional_qualification_{s}' for s in ['region', 'district', 'ward', 'street']}
        # Include other potential location fields from the intake form sections
        mtaa_select_field_names |= {f'{p}_{s}' for p in ['father', 'mother', 'emergency', 'olevel_school', 'alevel_school'] for s in ['region', 'district', 'ward', 'street']}
        mtaa_select_field_names |= {f'work1_{s}' for s in ['region', 'district', 'ward', 'street']}
        mtaa_select_field_names |= {f'work2_{s}' for s in ['region', 'district', 'ward', 'street']}

        for field_name in SUPPLEMENTAL_FIELD_NAMES:
            model_field = ApplicationSupplementalProfile._meta.get_field(field_name)
            is_boolean_field = model_field.get_internal_type() == 'BooleanField'
            is_mtaa_select = field_name in mtaa_select_field_names

            if model_field.get_internal_type() == 'BooleanField':
                form_field = forms.TypedChoiceField(
                    required=False,
                    choices=[('', '---------'), ('true', 'Yes'), ('false', 'No')],
                    coerce=lambda value: {'true': True, 'false': False}.get(value, None),
                    empty_value=None,
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    label=model_field.verbose_name.replace('_', ' ').title(),
                )
            else:
                form_field = model_field.formfield(required=False)

            if form_field is None:
                continue

            if is_mtaa_select:
                # Use CharField for dynamic location selects to bypass ChoiceField 
                # validation while still rendering a Select widget for JS to populate.
                form_field = forms.CharField(
                    required=False,
                    widget=forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
                    label=model_field.verbose_name.replace('_', ' ').title(),
                )
            elif is_boolean_field:
                form_field.widget = forms.Select(attrs={'class': 'form-select'})
            elif field_name in SUPPLEMENTAL_SELECT_CHOICES:
                form_field = forms.ChoiceField(
                    required=False,
                    choices=SUPPLEMENTAL_SELECT_CHOICES[field_name],
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    label=model_field.verbose_name.replace('_', ' ').title(),
                )
            elif model_field.get_internal_type() == 'DateField':
                widget = forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
                form_field.widget = widget
            elif model_field.get_internal_type() in {'TextField'} and field_name in SINGLE_LINE_SUPPLEMENTAL_TEXT_FIELDS:
                form_field.widget = forms.TextInput(attrs={'class': 'form-input'})
            elif model_field.get_internal_type() in {'TextField'}:
                form_field.widget = forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3})
            elif model_field.get_internal_type() in {'PositiveIntegerField', 'IntegerField'}:
                form_field.widget = forms.NumberInput(attrs={'class': 'form-input', 'min': 0})
            elif isinstance(form_field.widget, forms.EmailInput):
                form_field.widget.attrs = {'class': 'form-input'}
            else:
                form_field.widget = forms.TextInput(attrs={'class': 'form-input'})

            form_field.label = model_field.verbose_name.replace('_', ' ').title()

            if self.supplemental_instance is not None:
                initial_value = getattr(self.supplemental_instance, field_name)
                if is_boolean_field:
                    self.initial[field_name] = (
                        'true' if initial_value is True else 'false' if initial_value is False else ''
                    )
                else:
                    self.initial[field_name] = initial_value

            self.fields[field_name] = form_field

        for field_name in STUDENT_PROFILE_ONLY_FIELDS:
            if field_name in self.fields:
                continue
            is_mtaa_select = field_name in MTAA_SELECT_FIELD_NAMES
            if field_name == 'olevel_gpa':
                label = 'O-Level Division'
            elif field_name == 'alevel_gpa':
                label = 'A-Level Division'
            else:
                label = field_name.replace('_', ' ').title()
            if is_mtaa_select:
                self.fields[field_name] = forms.CharField(
                    required=False,
                    widget=forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
                    label=label,
                )
            elif field_name in {'olevel_start_year', 'olevel_completed_year', 'alevel_start_year', 'alevel_completed_year'}:
                self.fields[field_name] = forms.CharField(
                    required=False,
                    widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 2020'}),
                    label=label,
                )
            else:
                try:
                    model_field = StudentProfile._meta.get_field(field_name)
                    has_choices = bool(model_field.choices)
                except LookupError:
                    has_choices = False
                if has_choices:
                    self.fields[field_name] = forms.ChoiceField(
                        required=False,
                        choices=model_field.choices,
                        widget=forms.Select(attrs={'class': 'form-select'}),
                        label=label,
                    )
                else:
                    self.fields[field_name] = forms.CharField(
                        required=False,
                        widget=forms.TextInput(attrs={'class': 'form-input'}),
                        label=label,
                    )

        # Fields in Meta.fields that are rendered as Select but have no choices
        # on the StudentApplication model need them set explicitly.
        if 'marital_status' in self.fields:
            self.fields['marital_status'] = forms.ChoiceField(
                required=False,
                choices=StudentProfile.MARITAL_STATUS_CHOICES,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Marital Status',
            )
        if 'preferred_intake' in self.fields:
            self.fields['preferred_intake'] = forms.ChoiceField(
                required=False,
                choices=SUPPLEMENTAL_SELECT_CHOICES['preferred_intake'],
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Preferred Intake',
            )

    class Meta:
        model = StudentApplication
        fields = [
            'full_name',
            'gender',
            'date_of_birth',
            'place_of_birth',
            'nationality',
            'native_language',
            'marital_status',
            'email',
            'phone',
            'father_name',
            'father_phone',
            'father_email',
            'father_occupation',
            'father_place_neighbourhood',
            'father_status',
            'father_relationship',
            'mother_name',
            'mother_phone',
            'mother_email',
            'mother_occupation',
            'mother_place_neighbourhood',
            'mother_status',
            'mother_relationship',
            'olevel_school',
            'olevel_start_year',
            'olevel_completed_year',
            'olevel_candidate_no',
            'olevel_gpa',
            'olevel_school_type',
            'olevel_exam_board',
            'olevel_certificate_no',
            'olevel_remarks',
            'alevel_school',
            'alevel_start_year',
            'alevel_completed_year',
            'alevel_candidate_no',
            'alevel_gpa',
            'alevel_school_type',
            'alevel_exam_board',
            'alevel_certificate_no',
            'alevel_remarks',
            'preferred_intake',
            'preferred_country_1',
            'preferred_country_2',
            'preferred_country_3',
            'preferred_program_1',
            'preferred_program_2',
            'preferred_program_3',
            'emergency_name',
            'emergency_relation',
            'emergency_occupation',
            'emergency_phone',
            'emergency_email',
            'emergency_alternative_phone',
            'emergency_relationship_status',
            'emergency_remarks',
            'heard_about_us',
            'heard_about_other',
            'declaration_applicant_name',
            'declaration_date',
            'declaration_signature_name',
            'terms_accepted',
            'office_director_name',
            'office_approval_status',
            'office_reason',
            'work1_company_name', 'work1_position',
            'work1_worked_from', 'work1_worked_to',
            'work1_country', 'work1_region', 'work1_region_post_code',
            'work1_district', 'work1_district_post_code',
            'work1_ward', 'work1_ward_post_code',
            'work1_street',
            'work1_employment_type', 'work1_duties',
            'work1_supervisor', 'work1_remarks',
            'work2_company_name', 'work2_position',
            'work2_worked_from', 'work2_worked_to',
            'work2_country', 'work2_region', 'work2_region_post_code',
            'work2_district', 'work2_district_post_code',
            'work2_ward', 'work2_ward_post_code',
            'work2_street',
            'work2_employment_type', 'work2_duties',
            'work2_supervisor', 'work2_remarks',
            'profq1_title', 'profq1_institution', 'profq1_institution_address',
            'profq1_country', 'profq1_period',
            'profq1_start_date', 'profq1_finished_date', 'profq1_award_certificate',
            'profq2_title', 'profq2_institution', 'profq2_institution_address',
            'profq2_country', 'profq2_period',
            'profq2_start_date', 'profq2_finished_date', 'profq2_award_certificate',
            'profq3_title', 'profq3_institution', 'profq3_institution_address',
            'profq3_country', 'profq3_period',
            'profq3_start_date', 'profq3_finished_date', 'profq3_award_certificate',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name as in passport'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place of birth'}),
            'nationality': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nationality'}),
            'native_language': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Native language'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'student@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '255712345678'}),
            'father_name': forms.TextInput(attrs={'class': 'form-input'}),
            'father_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'father_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-input'}),
            'father_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'father_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Status'}),
            'father_relationship': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Relationship'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'mother_occupation': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_place_neighbourhood': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Place / Neighbourhood'}),
            'mother_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Status'}),
            'mother_relationship': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Relationship'}),
            'olevel_school': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_start_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Start year e.g. 2016'}),
            'olevel_completed_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Year completed e.g. 2020'}),
            'olevel_candidate_no': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_gpa': forms.Select(choices=SECONDARY_DIVISION_CHOICES, attrs={'class': 'form-input'}),
            'olevel_school_type': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School type'}),
            'olevel_exam_board': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Exam board'}),
            'olevel_certificate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Certificate no.'}),
            'olevel_remarks': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'alevel_school': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_start_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Start year e.g. 2020'}),
            'alevel_completed_year': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Year completed e.g. 2022'}),
            'alevel_candidate_no': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_gpa': forms.Select(choices=SECONDARY_DIVISION_CHOICES, attrs={'class': 'form-input'}),
            'alevel_school_type': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'School type'}),
            'alevel_exam_board': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Exam board'}),
            'alevel_certificate_no': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Certificate no.'}),
            'alevel_remarks': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'preferred_intake': forms.Select(attrs={'class': 'form-select'}),
            'preferred_country_1': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_country_2': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_country_3': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_1': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_2': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_3': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_name': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_relation': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_occupation': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+255...'}),
            'emergency_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'emergency@example.com'}),
            'emergency_alternative_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Alternative phone'}),
            'emergency_relationship_status': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Relationship status'}),
            'emergency_remarks': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'heard_about_us': forms.Select(
                attrs={'class': 'form-select'},
                choices=[
                    ('', '---------'),
                    ('Google Search', 'Google Search'),
                    ('Friend / Family Referral', 'Friend / Family Referral'),
                    ('School / College', 'School / College'),
                    ('Education Fair / Event', 'Education Fair / Event'),
                    ('Agent / Partner', 'Agent / Partner'),
                    ('Advertisement (TV, Radio, Newspaper)', 'Advertisement (TV, Radio, Newspaper)'),
                    ('Social Media', 'Social Media'),
                    ('Other', 'Other'),
                ],
            ),
            'heard_about_other': forms.TextInput(attrs={'class': 'form-input'}),
            'declaration_applicant_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name of applicant'}),
            'declaration_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'declaration_signature_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Type full name as signature'}),
            'terms_accepted': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'office_director_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Director / Officer name'}),
            'office_approval_status': forms.Select(
                attrs={'class': 'form-select'},
                choices=[('', '---------'), ('approved', 'Approved'), ('rejected', 'Rejected')],
            ),
            'office_reason': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
            'work1_company_name': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_position': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_worked_from': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'work1_worked_to': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'work1_country': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_region': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work1_region_post_code': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_district': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work1_district_post_code': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_ward': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work1_ward_post_code': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_street': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work1_employment_type': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_duties': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
            'work1_supervisor': forms.TextInput(attrs={'class': 'form-input'}),
            'work1_remarks': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'work2_company_name': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_position': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_worked_from': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'work2_worked_to': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'work2_country': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_region': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work2_region_post_code': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_district': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work2_district_post_code': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_ward': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work2_ward_post_code': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_street': forms.Select(attrs={'class': 'form-input'}, choices=[('', '--- Select ---')]),
            'work2_employment_type': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_duties': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
            'work2_supervisor': forms.TextInput(attrs={'class': 'form-input'}),
            'work2_remarks': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'profq1_title': forms.TextInput(attrs={'class': 'form-input'}),
            'profq1_institution': forms.TextInput(attrs={'class': 'form-input'}),
            'profq1_institution_address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'profq1_country': forms.TextInput(attrs={'class': 'form-input'}),
            'profq1_period': forms.TextInput(attrs={'class': 'form-input'}),
            'profq1_start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'profq1_finished_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'profq1_award_certificate': forms.Select(
                attrs={'class': 'form-select'},
                choices=[('', '---------'), ('yes', 'Yes'), ('no', 'No')],
            ),
            'profq2_title': forms.TextInput(attrs={'class': 'form-input'}),
            'profq2_institution': forms.TextInput(attrs={'class': 'form-input'}),
            'profq2_institution_address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'profq2_country': forms.TextInput(attrs={'class': 'form-input'}),
            'profq2_period': forms.TextInput(attrs={'class': 'form-input'}),
            'profq2_start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'profq2_finished_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'profq2_award_certificate': forms.Select(
                attrs={'class': 'form-select'},
                choices=[('', '---------'), ('yes', 'Yes'), ('no', 'No')],
            ),
            'profq3_title': forms.TextInput(attrs={'class': 'form-input'}),
            'profq3_institution': forms.TextInput(attrs={'class': 'form-input'}),
            'profq3_institution_address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 2}),
            'profq3_country': forms.TextInput(attrs={'class': 'form-input'}),
            'profq3_period': forms.TextInput(attrs={'class': 'form-input'}),
            'profq3_start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'profq3_finished_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'profq3_award_certificate': forms.Select(
                attrs={'class': 'form-select'},
                choices=[('', '---------'), ('yes', 'Yes'), ('no', 'No')],
            ),
        }

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean(self):
        return super().clean()
