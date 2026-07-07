from django.contrib import admin
from .models import Document


class DocumentAdmin(admin.ModelAdmin):
    list_display = ['document_type', 'student', 'application', 'uploaded_at', 'is_verified']
    list_filter = ['document_type', 'is_verified', 'application']
    search_fields = ['student__username', 'student__first_name', 'student__last_name', 'document_type']


admin.site.register(Document, DocumentAdmin)
