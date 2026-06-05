"""
Password Reset Views for Student Portal
"""
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse
from django.conf import settings

def student_forgot_password(request):
    """Student forgot password - request reset"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Create reset link
            reset_link = request.build_absolute_uri(
                reverse('student_portal:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            )
            
            # Send email
            subject = 'Password Reset Request - Africa Western Education'
            message = f"""
Hello {user.first_name},

You have requested to reset your password for your student portal account.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this reset, please ignore this email.

Best regards,
Africa Western Education Team
            """
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@africawesternedu.com',
                    [email],
                    fail_silently=False,
                )
                messages.success(request, 'Password reset link has been sent to your email.')
            except Exception as e:
                # If email fails, show console message and still provide success feedback
                print(f"Email sending failed: {e}")
                print(f"Reset link: {reset_link}")
                messages.success(request, 'Password reset instructions have been generated. Check the console for the reset link.')
            
            return redirect('student_portal:login')
            
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
    
    return render(request, 'student_portal/forgot_password.html')


def student_password_reset_confirm(request, uidb64, token):
    """Student password reset confirmation"""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')

            if not password1 or not password2:
                messages.error(request, 'Please enter and confirm your new password.')
            elif password1 != password2:
                messages.error(request, 'Passwords do not match.')
            else:
                try:
                    validate_password(password1, user=user)
                except ValidationError as exc:
                    for error in exc.messages:
                        messages.error(request, error)
                else:
                    user.set_password(password1)
                    user.save()
                    messages.success(request, 'Your password has been reset successfully. You can now login.')
                    return redirect('student_portal:login')

            return redirect(
                'student_portal:password_reset_confirm',
                uidb64=uidb64,
                token=token,
            )

        return render(request, 'student_portal/password_reset_confirm.html', {
            'validlink': True,
            'uidb64': uidb64,
            'token': token
        })
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('student_portal:forgot_password')
