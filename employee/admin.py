from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django import forms
from .models import ApplicationAssignment, EmployeeProfile, PortalUpdate, UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fields = ('role', 'registration_method', 'department', 'position', 'employee_id', 'phone_number')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # If creating a new user, set default role to student
        if obj is None:
            formset.form.base_fields['role'].initial = 'student'
            formset.form.base_fields['registration_method'].initial = 'self'
        return formset

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'get_registration_method', 'is_staff', 'is_active')
    list_filter = ('userprofile__role', 'userprofile__registration_method', 'is_staff', 'is_active')
    actions = ['convert_to_employee', 'convert_to_student']
    
    def get_role(self, obj):
        try:
            return obj.userprofile.get_role_display()
        except UserProfile.DoesNotExist:
            return "No role"
    get_role.short_description = 'Role'
    
    def get_registration_method(self, obj):
        try:
            return obj.userprofile.get_registration_method_display()
        except UserProfile.DoesNotExist:
            return "Unknown"
    get_registration_method.short_description = 'Registration Method'
    
    def convert_to_employee(self, request, queryset):
        for user in queryset:
            try:
                profile = user.userprofile
                profile.role = 'employee'
                profile.registration_method = 'admin'
                if not profile.department:
                    profile.department = 'General'
                if not profile.position:
                    profile.position = 'Employee'
                profile.save()
                self.message_user(request, f"Converted {user.username} to employee")
            except UserProfile.DoesNotExist:
                UserProfile.objects.create(
                    user=user,
                    role='employee',
                    registration_method='admin',
                    department='General',
                    position='Employee'
                )
                self.message_user(request, f"Created employee profile for {user.username}")
    convert_to_employee.short_description = "Convert selected users to employees"
    
    def convert_to_student(self, request, queryset):
        for user in queryset:
            try:
                profile = user.userprofile
                profile.role = 'student'
                profile.registration_method = 'self'
                profile.save()
                self.message_user(request, f"Converted {user.username} to student")
            except UserProfile.DoesNotExist:
                UserProfile.objects.create(
                    user=user,
                    role='student',
                    registration_method='self'
                )
                self.message_user(request, f"Created student profile for {user.username}")
    convert_to_student.short_description = "Convert selected users to students"

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'registration_method', 'department', 'position', 'employee_id', 'created_at')
    list_filter = ('role', 'registration_method', 'department', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'employee_id')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('role', 'department', 'position')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Show all profiles to admin
        return qs

@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'department', 'position', 'employee_id', 'created_at')
    list_filter = ('department', 'position', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'employee_id')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ApplicationAssignment)
class ApplicationAssignmentAdmin(admin.ModelAdmin):
    list_display = ('application', 'employee', 'assigned_date', 'status')
    list_filter = ('status', 'assigned_date')
    search_fields = ('application__student__username', 'employee__username')
    readonly_fields = ('assigned_date',)
    list_editable = ('status',)


@admin.register(PortalUpdate)
class PortalUpdateAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'content_type',
        'status',
        'featured_on_homepage',
        'author',
        'published_at',
        'updated_at',
    )
    list_filter = ('content_type', 'status', 'featured_on_homepage', 'published_at')
    search_fields = ('title', 'excerpt', 'content', 'location', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'published_at')

# Custom admin site configuration
admin.site.site_header = "Employee Portal Administration"
admin.site.site_title = "Employee Portal Admin"
admin.site.index_title = "Welcome to Employee Portal Administration"

class EmployeeAdminSite(admin.AdminSite):
    site_header = "Employee Management"
    site_title = "Employee Portal"
    index_title = "Employee Administration"

# Optional: Separate admin site for employee management
employee_admin = EmployeeAdminSite(name='employee_admin')
