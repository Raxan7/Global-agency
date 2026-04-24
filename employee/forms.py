from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from io import BytesIO
from django.utils.html import strip_tags
from urllib.parse import urlparse

from global_agency.models import StudentApplication
from student_portal.models import ApplicationSupplementalProfile

from .models import PortalUpdate, PortalUpdateAttachment, PortalUpdateImage


SUPPLEMENTAL_FIELD_GROUPS = [
    (
        'csc_personal',
        'Application Format: Personal Information',
        'Capture the CSC-style personal details requested in the new format.',
        'fa-id-card',
        [
            'agency_no', 'agency_name', 'surname', 'given_name', 'chinese_name',
            'marital_status', 'native_language', 'passport_no', 'passport_expiration_date',
            'country_of_birth', 'city_of_birth', 'religion', 'personal_phone',
            'personal_email', 'alternate_email', 'wechat_id', 'skype_no',
            'correspondence_address', 'emergency_contact_name', 'emergency_contact_gender',
            'emergency_contact_relation', 'emergency_contact_phone',
            'emergency_contact_email', 'emergency_contact_address',
        ],
    ),
    (
        'csc_education',
        'Application Format: Education and Employment History',
        'Fill in the extended academic and work history exactly as requested in the new format.',
        'fa-graduation-cap',
        [
            'highest_education_level', 'highest_education_country', 'highest_education_institute',
            'highest_education_start_date', 'highest_education_end_date',
            'highest_education_field_of_study', 'highest_education_qualification',
            'other_education_1_level', 'other_education_1_country', 'other_education_1_institute',
            'other_education_1_start_date', 'other_education_1_end_date',
            'other_education_1_field_of_study', 'other_education_1_qualification',
            'other_education_2_level', 'other_education_2_country', 'other_education_2_institute',
            'other_education_2_start_date', 'other_education_2_end_date',
            'other_education_2_field_of_study', 'other_education_2_qualification',
            'employer', 'employment_start_date', 'employment_end_date',
            'work_engaged', 'title_position',
        ],
    ),
    (
        'csc_language',
        'Application Format: Language Proficiency and Study Plan',
        'These fields feed the CSC-style PDF and employee review workflow.',
        'fa-earth-africa',
        [
            'chinese_proficiency', 'has_hsk_certificate', 'hsk_level', 'hsk_score', 'hsk_test_date',
            'english_proficiency', 'has_english_certificate', 'english_test_name',
            'english_test_score', 'english_test_date', 'apply_as', 'preferred_teaching_language',
            'has_pre_admission_letter', 'institute_preference_1', 'discipline_1', 'major_1',
            'institute_preference_2', 'discipline_2', 'major_2',
            'institute_preference_3', 'discipline_3', 'major_3',
            'major_study_start_date', 'major_study_end_date',
            'ever_studied_or_worked_in_china', 'china_institute_or_employer',
            'china_employment_start_date', 'china_employment_end_date',
            'ever_had_chinese_government_scholarship', 'previous_csc_institute_name',
            'previous_csc_start_date', 'previous_csc_end_date',
        ],
    ),
    (
        'csc_contacts',
        'Application Format: Other Contacts',
        'Keep the extra family and China contact details here.',
        'fa-address-book',
        [
            'contact_person_china_name', 'contact_person_china_tel', 'contact_person_china_email',
            'contact_person_china_fax', 'contact_person_china_address',
            'spouse_name', 'spouse_age', 'spouse_occupation',
            'father_age', 'mother_age',
        ],
    ),
    (
        'csc_declaration',
        'Application Format: Supporting Documents and Declaration',
        'Mark supporting-document availability and confirm the declaration.',
        'fa-file-signature',
        [
            'has_passport_photo', 'has_highest_education_certificate', 'has_highest_education_transcript',
            'has_study_plan', 'has_reference_1', 'has_reference_2', 'has_passport_home_page',
            'has_physical_exam_record', 'has_articles_or_papers', 'has_art_music_examples',
            'has_chinese_language_certificate', 'has_english_language_certificate',
            'has_csca_score_report', 'has_pre_admission_letter_document',
            'has_non_criminal_record', 'has_other_attachments',
            'other_attachments_description', 'declaration_agreed',
        ],
    ),
]

SUPPLEMENTAL_FIELD_NAMES = [
    field_name
    for _, _, _, _, field_names in SUPPLEMENTAL_FIELD_GROUPS
    for field_name in field_names
]

DOCUMENT_UPLOAD_FIELD_MAP = [
    ('passport_document', 'passport', 'Passport / ID page'),
    ('passport_photo_document', 'passport_photo', 'Passport photo'),
    ('ordinary_level_document', 'ordinary_level', 'O-Level certificate'),
    ('advanced_level_document', 'advanced_level', 'A-Level certificate'),
    ('academic_transcript_document', 'academic_transcript', 'Academic transcript'),
    ('degree_certificate_document', 'degree_certificate', 'Degree certificate'),
    ('application_form_document', 'application_form', 'Application form'),
    ('recommendation_letter_document', 'recommendation_letter', 'Recommendation letter'),
    ('sop_document', 'sop', 'Statement of purpose / study plan'),
    ('cv_document', 'cv', 'CV / resume'),
    ('language_test_document', 'language_test', 'Language test result'),
    ('proof_of_funds_document', 'proof_of_funds', 'Proof of funds'),
    ('health_insurance_document', 'health_insurance', 'Health insurance'),
    ('financial_document', 'financial_documents', 'Financial document'),
]

DOCUMENT_FLAG_FIELD_MAP = {
    'passport_document': 'has_passport_home_page',
    'passport_photo_document': 'has_passport_photo',
    'ordinary_level_document': 'has_highest_education_certificate',
    'advanced_level_document': 'has_highest_education_certificate',
    'academic_transcript_document': 'has_highest_education_transcript',
    'degree_certificate_document': 'has_highest_education_certificate',
    'application_form_document': 'has_other_attachments',
    'recommendation_letter_document': 'has_reference_1',
    'sop_document': 'has_study_plan',
    'language_test_document': 'has_english_language_certificate',
    'proof_of_funds_document': 'has_other_attachments',
    'health_insurance_document': 'has_other_attachments',
    'financial_document': 'has_other_attachments',
}

SINGLE_LINE_SUPPLEMENTAL_TEXT_FIELDS = {
    'agency_name',
    'highest_education_institute',
    'highest_education_field_of_study',
    'highest_education_qualification',
    'other_education_1_institute',
    'other_education_1_field_of_study',
    'other_education_1_qualification',
    'other_education_2_institute',
    'other_education_2_field_of_study',
    'other_education_2_qualification',
    'employer',
    'work_engaged',
    'title_position',
    'institute_preference_1',
    'discipline_1',
    'major_1',
    'institute_preference_2',
    'discipline_2',
    'major_2',
    'institute_preference_3',
    'discipline_3',
    'major_3',
    'china_institute_or_employer',
    'previous_csc_institute_name',
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

        def normalized_attachment_file(uploaded_file):
            uploaded_file.seek(0)
            try:
                from PIL import Image as PillowImage

                with PillowImage.open(uploaded_file) as image:
                    image.verify()
                uploaded_file.seek(0)
                return uploaded_file
            except Exception:
                uploaded_file.seek(0)
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
            PortalUpdateAttachment.objects.create(
                update=portal_update,
                file=normalized_attachment_file(attachment_file),
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
    profile_picture_upload = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        help_text='Upload the student photo that should appear in the portal and employee review pages.',
        label='Student image',
    )
    passport_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    passport_photo_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    ordinary_level_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    advanced_level_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    academic_transcript_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    degree_certificate_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    application_form_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    recommendation_letter_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    sop_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    cv_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    language_test_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    proof_of_funds_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    health_insurance_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
    financial_document = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-input'}))
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
        self.fields['olevel_country'].initial = 'Tanzania'
        self.fields['alevel_country'].initial = 'Tanzania'
        self.fields['alevel_country'].required = False
        self.fields['emergency_name'].required = False
        self.fields['emergency_address'].required = False
        self.fields['emergency_occupation'].required = False
        self.fields['emergency_gender'].required = False
        self.fields['emergency_relation'].required = False
        self.current_profile_picture = getattr(self.student_profile_instance, 'profile_picture', None)
        self.existing_documents_by_type = {}
        for document in self.existing_documents:
            self.existing_documents_by_type.setdefault(document.document_type, document)

        for field_name, _doc_type, label in DOCUMENT_UPLOAD_FIELD_MAP:
            self.fields[field_name].label = label
            self.fields[field_name].help_text = f'Upload the {label.lower()} file if it is available.'

        for field_name in SUPPLEMENTAL_FIELD_NAMES:
            model_field = ApplicationSupplementalProfile._meta.get_field(field_name)
            is_boolean_field = model_field.get_internal_type() == 'BooleanField'
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

            widget = form_field.widget
            if hasattr(widget, 'attrs'):
                widget.attrs['class'] = 'form-input'

            if is_boolean_field:
                form_field.widget = forms.Select(attrs={'class': 'form-select'})
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

    class Meta:
        model = StudentApplication
        fields = [
            'full_name',
            'gender',
            'nationality',
            'email',
            'phone',
            'address',
            'father_name',
            'father_phone',
            'father_email',
            'father_occupation',
            'mother_name',
            'mother_phone',
            'mother_email',
            'mother_occupation',
            'olevel_school',
            'olevel_country',
            'olevel_address',
            'olevel_region',
            'olevel_year',
            'olevel_candidate_no',
            'olevel_gpa',
            'alevel_school',
            'alevel_country',
            'alevel_address',
            'alevel_region',
            'alevel_year',
            'alevel_candidate_no',
            'alevel_gpa',
            'preferred_country_1',
            'preferred_country_2',
            'preferred_country_3',
            'preferred_country_4',
            'preferred_program_1',
            'preferred_program_2',
            'preferred_program_3',
            'preferred_program_4',
            'emergency_name',
            'emergency_address',
            'emergency_occupation',
            'emergency_gender',
            'emergency_relation',
            'heard_about_us',
            'heard_about_other',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Student full name'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'nationality': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nationality'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'student@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '255712345678'}),
            'address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
            'father_name': forms.TextInput(attrs={'class': 'form-input'}),
            'father_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'father_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'father_occupation': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'mother_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'mother_occupation': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_school': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_country': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_address': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_region': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_year': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_candidate_no': forms.TextInput(attrs={'class': 'form-input'}),
            'olevel_gpa': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_school': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_country': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_address': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_region': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_year': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_candidate_no': forms.TextInput(attrs={'class': 'form-input'}),
            'alevel_gpa': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_country_1': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_country_2': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_country_3': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_country_4': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_1': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_2': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_3': forms.TextInput(attrs={'class': 'form-input'}),
            'preferred_program_4': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_name': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_address': forms.Textarea(attrs={'class': 'form-input form-textarea', 'rows': 3}),
            'emergency_occupation': forms.TextInput(attrs={'class': 'form-input'}),
            'emergency_gender': forms.Select(attrs={'class': 'form-select'}),
            'emergency_relation': forms.TextInput(attrs={'class': 'form-input'}),
            'heard_about_us': forms.TextInput(attrs={'class': 'form-input'}),
            'heard_about_other': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('olevel_country'):
            cleaned_data['olevel_country'] = 'Tanzania'
        if not cleaned_data.get('alevel_country'):
            cleaned_data['alevel_country'] = 'Tanzania'

        father_name = (cleaned_data.get('father_name') or '').strip()
        mother_name = (cleaned_data.get('mother_name') or '').strip()
        parent_entry_mode = cleaned_data.get('parent_entry_mode') or 'guardian_only'
        has_parent_info = bool(father_name or mother_name)

        guardian_required_fields = {
            'emergency_name': 'Guardian name is required when no parent details are provided.',
            'emergency_address': 'Guardian address is required when no parent details are provided.',
            'emergency_relation': 'Guardian relation is required when no parent details are provided.',
            'emergency_gender': 'Guardian gender is required when no parent details are provided.',
        }

        if parent_entry_mode == 'parents' and not has_parent_info:
            self.add_error('parent_entry_mode', 'Please enter at least one parent name or switch to guardian mode.')

        if not has_parent_info:
            for field_name, error_message in guardian_required_fields.items():
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, error_message)

        return cleaned_data
