from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps
from .models import UserProfile

def employee_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('employee:employee_login')
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            # CHANGED: Use can_access_employee_portal() instead of is_employee()
            if not profile.can_access_employee_portal():
                return HttpResponseForbidden("Access denied. Admin-created employee account required. Please use the student portal for student access.")
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("Access denied. User profile not found. Please contact administrator.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def partner_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('employee:partner_login')

        try:
            profile = UserProfile.objects.get(user=request.user)
            if not profile.can_access_partner_portal():
                return HttpResponseForbidden("Access denied. Verified partner account required.")
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("Access denied. User profile not found. Please contact administrator.")

        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('employee:employee_login')
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            if not profile.is_admin():
                return HttpResponseForbidden("Access denied. Administrator account required.")
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("Access denied. User profile not found.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_created_employee_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('employee:employee_login')
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            if not profile.is_admin_created_employee():
                return HttpResponseForbidden("Access denied. Admin-created employee account required.")
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("Access denied. User profile not found.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# ADD THIS NEW DECORATOR FOR STUDENT PORTAL
def student_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('student:student_login')
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            if not profile.can_access_student_portal():
                return HttpResponseForbidden("Access denied. A student account is required. Please use the employee portal for employee access.")
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("Access denied. User profile not found. Please contact administrator.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
