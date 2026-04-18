from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from urllib.parse import urlparse

from global_agency.models import StudentApplication

from .models import PortalUpdate, PortalUpdateAttachment, PortalUpdateImage


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
        for image in self.cleaned_data.get('remove_gallery_images', []):
            image.delete()

        for attachment in self.cleaned_data.get('remove_attachments', []):
            attachment.delete()

        for image_file in self.cleaned_data.get('gallery_images', []):
            PortalUpdateImage.objects.create(
                update=portal_update,
                image=image_file,
                alt_text=portal_update.image_alt_text,
            )

        for attachment_file in self.cleaned_data.get('attachments', []):
            PortalUpdateAttachment.objects.create(
                update=portal_update,
                file=attachment_file,
                title=attachment_file.name.rsplit('/', 1)[-1],
            )


class OfflineStudentIntakeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['olevel_country'].initial = 'Tanzania'
        self.fields['alevel_country'].initial = 'Tanzania'
        self.fields['alevel_country'].required = False

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
        return cleaned_data
