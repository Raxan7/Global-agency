from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pathlib import Path

from employee.models import UserProfile


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class EmployeePasswordResetTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='employee@example.com',
            email='employee@example.com',
            password='OldPassword123!',
            first_name='Asha',
        )
        UserProfile.objects.create(
            user=self.employee_user,
            role='employee',
            registration_method='admin',
        )

        self.student_user = User.objects.create_user(
            username='student@example.com',
            email='student@example.com',
            password='OldPassword123!',
        )
        UserProfile.objects.create(
            user=self.student_user,
            role='student',
            registration_method='self',
        )

    def test_login_page_contains_forgot_password_link(self):
        template_path = Path(__file__).resolve().parent / 'templates' / 'employee' / 'login.html'
        template_source = template_path.read_text(encoding='utf-8')

        self.assertIn("{% url 'employee:forgot_password' %}", template_source)

    def test_employee_can_request_reset_link_with_case_insensitive_email(self):
        response = self.client.post(
            reverse('employee:forgot_password'),
            {'email': 'EMPLOYEE@example.com'},
        )

        self.assertRedirects(response, reverse('employee:employee_login'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/employee/reset-password/', mail.outbox[0].body)

    def test_non_employee_cannot_request_employee_reset(self):
        response = self.client.post(
            reverse('employee:forgot_password'),
            {'email': 'student@example.com'},
        )

        self.assertRedirects(response, reverse('employee:forgot_password'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)

    def test_employee_can_reset_password_from_valid_link(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.employee_user.pk))
        token = default_token_generator.make_token(self.employee_user)

        response = self.client.post(
            reverse(
                'employee:password_reset_employee_confirm',
                kwargs={'uidb64': uidb64, 'token': token},
            ),
            {'password1': 'NewStrongPass123!', 'password2': 'NewStrongPass123!'},
        )

        self.assertRedirects(response, reverse('employee:employee_login'), fetch_redirect_response=False)
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.check_password('NewStrongPass123!'))

    def test_reset_rejects_mismatched_passwords(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.employee_user.pk))
        token = default_token_generator.make_token(self.employee_user)

        response = self.client.post(
            reverse(
                'employee:password_reset_employee_confirm',
                kwargs={'uidb64': uidb64, 'token': token},
            ),
            {'password1': 'NewStrongPass123!', 'password2': 'WrongPass123!'},
        )

        self.assertRedirects(
            response,
            reverse(
                'employee:password_reset_employee_confirm',
                kwargs={'uidb64': uidb64, 'token': token},
            ),
            fetch_redirect_response=False,
        )
        self.employee_user.refresh_from_db()
        self.assertTrue(self.employee_user.check_password('OldPassword123!'))
