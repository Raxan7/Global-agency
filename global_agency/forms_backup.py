from django import forms
class ContactForm(forms.ModelForm):
    from django import forms
from .models import ContactMessage

class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'destination', 'message']



from .models import StudentApplication

class StudentApplicationForm(forms.ModelForm):
    class Meta:
        model = StudentApplication
        fields = '__all__'
        widgets = {
            'emergency_address': forms.Textarea(attrs={'rows':2}),
            'heard_about_other': forms.TextInput(),
        }
        




