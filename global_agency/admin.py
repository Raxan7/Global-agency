from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import ContactMessage, StudentApplication, Student, StudentProfile

# Student Profile Inline
class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'Student Profile'
    fields = ('phone', 'date_of_birth', 'emergency_contact', 'emergency_phone')
    readonly_fields = ()

# Student Applications Inline
class StudentApplicationInline(admin.TabularInline):
    model = StudentApplication
    fk_name = 'student_user'
    extra = 0
    max_num = 5
    fields = ('full_name', 'email', 'nationality', 'created_at', 'account_created')
    readonly_fields = ('created_at', 'account_created')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

# Custom User Admin to show student-related information
class CustomUserAdmin(UserAdmin):
    def get_inlines(self, request, obj=None):
        if obj and StudentApplication.objects.filter(email=obj.email).exists():
            return [StudentProfileInline, StudentApplicationInline]
        return []

# Student Proxy Model Admin
@admin.register(Student)
class StudentAdmin(UserAdmin):
    """Admin interface for Student proxy model - shows only student users"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_phone', 'date_joined', 'is_active')
    list_filter = ('is_active', 'date_joined', 'last_login')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_active', 'is_staff'),
        }),
    )
    
    inlines = [StudentProfileInline, StudentApplicationInline]
    
    def get_queryset(self, request):
        # Only show non-staff, non-superuser accounts that have student applications
        qs = super().get_queryset(request)
        student_emails = StudentApplication.objects.values_list('email', flat=True).distinct()
        return qs.filter(
            email__in=student_emails,
            is_staff=False,
            is_superuser=False
        )
    
    def get_phone(self, obj):
        if hasattr(obj, 'student_profile') and obj.student_profile.phone:
            return obj.student_profile.phone
        return "Not set"
    get_phone.short_description = 'Phone'
    
    def has_applications(self, obj):
        return StudentApplication.objects.filter(email=obj.email).exists()
    has_applications.boolean = True
    has_applications.short_description = 'Has Applications'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'destination', 'created_at', 'handled')
    list_filter = ('handled', 'destination', 'created_at')
    search_fields = ('name', 'email', 'phone', 'message', 'destination')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'destination')
        }),
        ('Message Details', {
            'fields': ('message', 'handled', 'created_at')
        }),
    )
    
    actions = ['mark_as_handled', 'mark_as_pending']
    
    def mark_as_handled(self, request, queryset):
        queryset.update(handled=True)
    mark_as_handled.short_description = "Mark selected messages as handled"
    
    def mark_as_pending(self, request, queryset):
        queryset.update(handled=False)
    mark_as_pending.short_description = "Mark selected messages as pending"

@admin.register(StudentApplication)
class StudentApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'email',
        'phone',
        'nationality',
        'account_created',
        'created_at',
        'has_student_account',
    )
    list_filter = (
        'gender',
        'nationality',
        'emergency_gender',
        'account_created',
        'created_at',
    )
    search_fields = (
        'full_name',
        'email',
        'phone',
        'father_name',
        'mother_name',
        'emergency_name',
    )
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'account_created', 'username', 'temporary_password')
    
    fieldsets = (
        ('Personal Information', {
            'fields': (
                'full_name', 'gender', 'nationality', 'email', 'phone', 'address'
            )
        }),
        ('Parents Details', {
            'fields': (
                'father_name', 'father_phone', 'father_email', 'father_occupation',
                'mother_name', 'mother_phone', 'mother_email', 'mother_occupation'
            ),
            'classes': ('collapse',)
        }),
        ('Education Background - O-Level', {
            'fields': (
                'olevel_school', 'olevel_country', 'olevel_address', 'olevel_region',
                'olevel_year', 'olevel_candidate_no', 'olevel_gpa'
            ),
            'classes': ('collapse',)
        }),
        ('Education Background - A-Level', {
            'fields': (
                'alevel_school', 'alevel_country', 'alevel_address', 'alevel_region',
                'alevel_year', 'alevel_candidate_no', 'alevel_gpa'
            ),
            'classes': ('collapse',)
        }),
        ('Study Preferences', {
            'fields': (
                'preferred_country_1', 'preferred_country_2', 'preferred_country_3', 'preferred_country_4',
                'preferred_program_1', 'preferred_program_2', 'preferred_program_3', 'preferred_program_4'
            ),
            'classes': ('collapse',)
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_name', 'emergency_address', 'emergency_occupation',
                'emergency_gender', 'emergency_relation', 'heard_about_us', 'heard_about_other'
            ),
            'classes': ('collapse',)
        }),
        ('Account Information', {
            'fields': (
                'account_created', 'username', 'temporary_password', 'student_user'
            ),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('created_at',),
        }),
    )
    
    def has_student_account(self, obj):
        return obj.account_created
    has_student_account.boolean = True
    has_student_account.short_description = 'Account Created'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student_user')
    
    actions = ['create_student_accounts']
    
    def create_student_accounts(self, request, queryset):
        """Admin action to create student accounts for selected applications"""
        success_count = 0
        for application in queryset:
            if not application.account_created:
                student_user = application.create_student_account()
                if student_user:
                    success_count += 1
        
        if success_count > 0:
            self.message_user(request, f"Successfully created {success_count} student account(s)")
        else:
            self.message_user(request, "No new accounts were created (they may already exist)")
    create_student_accounts.short_description = "Create student accounts for selected applications"

# Register StudentProfile separately if needed
@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'date_of_birth', 'emergency_contact')
    search_fields = ('user__username', 'user__email', 'phone', 'emergency_contact')
    list_filter = ('date_of_birth',)
    raw_id_fields = ('user',)

# Unregister default User admin and register with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)