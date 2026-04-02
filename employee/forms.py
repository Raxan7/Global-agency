from django import forms

from .models import PortalUpdate


class PortalUpdateForm(forms.ModelForm):
    class Meta:
        model = PortalUpdate
        fields = [
            'content_type',
            'title',
            'excerpt',
            'content',
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
                    'class': 'form-input form-textarea',
                    'rows': 10,
                    'placeholder': 'Add the full story, event details, or image context here',
                }
            ),
            'cover_image': forms.ClearableFileInput(attrs={'class': 'form-input'}),
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

    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get('content_type')
        cover_image = cleaned_data.get('cover_image') or getattr(self.instance, 'cover_image', None)
        event_start = cleaned_data.get('event_start')
        event_end = cleaned_data.get('event_end')

        if content_type == 'image' and not cover_image:
            self.add_error('cover_image', 'An image is required for image story updates.')

        if content_type == 'event' and not event_start:
            self.add_error('event_start', 'Events need a start date and time.')

        if event_start and event_end and event_end < event_start:
            self.add_error('event_end', 'Event end time must be after the start time.')

        return cleaned_data
