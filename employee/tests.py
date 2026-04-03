from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pathlib import Path

from global_agency.models import StudentApplication
from employee.models import UserProfile
from student_portal.models import Application, StudentProfile


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


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class OfflineStudentIntakeTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='employee@example.com',
            email='employee@example.com',
            password='EmployeePass123!',
            first_name='Musa',
            last_name='Staff',
        )
        UserProfile.objects.create(
            user=self.employee_user,
            role='employee',
            registration_method='admin',
        )

    def test_employee_can_create_offline_student_account_and_application(self):
        self.client.login(username='employee@example.com', password='EmployeePass123!')

        response = self.client.post(
            reverse('employee:offline_application_create'),
            {
                'full_name': 'Asha Mollel',
                'gender': 'female',
                'nationality': 'Tanzanian',
                'email': 'asha@example.com',
                'phone': '255712345678',
                'address': 'Arusha, Tanzania',
                'olevel_school': 'Arusha Secondary School',
                'olevel_country': 'Tanzania',
                'olevel_address': 'Arusha',
                'olevel_region': 'Arusha',
                'olevel_year': '2022',
                'olevel_candidate_no': 'S1234/2022/0001',
                'olevel_gpa': 'Division I',
                'preferred_country_1': 'Canada',
                'preferred_program_1': 'Computer Science',
                'emergency_name': 'Neema Mollel',
                'emergency_address': 'Moshi, Tanzania',
                'emergency_occupation': 'Teacher',
                'emergency_gender': 'female',
                'emergency_relation': 'Mother',
                'heard_about_us': 'Referral',
            },
        )

        student_user = User.objects.get(username='asha@example.com')
        student_profile = StudentProfile.objects.get(user=student_user)
        application = Application.objects.get(student=student_user)
        offline_application = StudentApplication.objects.get(email='asha@example.com')

        self.assertRedirects(
            response,
            reverse('employee:student_application_detail', kwargs={'application_id': application.id}),
            fetch_redirect_response=False,
        )
        self.assertTrue(student_user.check_password('ASHA12345'))
        self.assertEqual(student_user.first_name, 'Asha')
        self.assertEqual(student_profile.preferred_country_1, 'Canada')
        self.assertEqual(student_profile.preferred_program_1, 'Computer Science')
        self.assertEqual(application.status, 'submitted')
        self.assertTrue(application.is_paid)
        self.assertEqual(application.payment_status, 'paid')
        self.assertEqual(offline_application.temporary_password, 'ASHA12345')
        self.assertTrue(offline_application.account_created)
        self.assertEqual(student_user.userprofile.registration_method, 'admin')
