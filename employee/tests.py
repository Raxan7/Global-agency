from datetime import date, timedelta
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from io import BytesIO
from pathlib import Path
import shutil
import tempfile

from global_agency.models import ContactMessage, StudentApplication
from employee.forms import PortalUpdateForm
from employee.models import PortalUpdate, PortalUpdateAttachment, UserProfile
from employee.awec_csc_exact_style_django_pdf_export import (
    application_to_awec_csc_style_data,
    generate_pdf,
    build_awec_csc_style_application_pdf_response,
)
from student_portal.models import (
    Application,
    ApplicationSupplementalProfile,
    Document,
    StudentProfile,
    WorkExperience,
)

VALID_GIF_BYTES = (
    b'GIF87a\x01\x00\x01\x00\x80\x00\x00'
    b'\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,'
    b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)

TEST_FILE_STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


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
    DEFAULT_FROM_EMAIL='African Western Education <support@africawesterneducation.com>',
    EMAIL_HOST_PASSWORD='',
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)

class EmployeeContactReplyEmailTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='employee@example.com',
            email='employee@example.com',
            password='EmployeePass123!',
            first_name='Musa',
        )
        UserProfile.objects.create(
            user=self.employee_user,
            role='employee',
            registration_method='admin',
        )
        self.contact_message = ContactMessage.objects.create(
            name='Asha Mollel',
            email='asha@example.com',
            phone='255712345678',
            message='I need consultation support.',
        )

    def test_employee_reply_uses_default_email_configuration(self):
        self.client.login(username='employee@example.com', password='EmployeePass123!')

        response = self.client.post(
            reverse(
                'employee:reply_to_message',
                kwargs={'message_id': self.contact_message.id, 'channel': 'email'},
            ),
            {
                'subject': 'Re: Consultation',
                'reply_message': 'Thank you for contacting us. We will assist you shortly.',
            },
        )

        self.assertRedirects(response, reverse('employee:contact_messages'), fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'African Western Education <support@africawesterneducation.com>')
        self.assertEqual(mail.outbox[0].to, ['asha@example.com'])
        self.assertIn('Thank you for contacting us.', mail.outbox[0].body)

        self.contact_message.refresh_from_db()
        self.assertTrue(self.contact_message.handled)
        self.assertEqual(self.contact_message.reply_subject, 'Re: Consultation')
        self.assertEqual(self.contact_message.replied_by, self.employee_user)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
@override_settings(STORAGES=TEST_FILE_STORAGES)
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
                'olevel_school_country': 'Tanzania',
                'olevel_school_region': 'Arusha',
                'olevel_completed_year': '2022',
                'olevel_candidate_no': 'S1234/2022/0001',
                'olevel_gpa': 'Division I',
                'preferred_country_1': 'Canada',
                'preferred_program_1': 'Computer Science',
                'emergency_name': 'Neema Mollel',
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

    def test_employee_intake_uploads_profile_and_document_files(self):
        self.client.login(username='employee@example.com', password='EmployeePass123!')

        payload = {
            'full_name': 'Asha Mollel',
            'gender': 'female',
            'nationality': 'Tanzanian',
            'email': 'asha.uploads@example.com',
            'phone': '255712345678',
            'address': 'Arusha, Tanzania',
            'olevel_school': 'Arusha Secondary School',
            'olevel_school_country': 'Tanzania',
            'olevel_school_region': 'Arusha',
            'olevel_completed_year': '2022',
            'olevel_candidate_no': 'S1234/2022/0001',
            'olevel_gpa': 'Division I',
            'preferred_country_1': 'Canada',
            'preferred_program_1': 'Computer Science',
            'emergency_name': 'Neema Mollel',
            'emergency_occupation': 'Teacher',
            'emergency_gender': 'female',
            'emergency_relation': 'Mother',
            'heard_about_us': 'Referral',
            'profile_picture_upload': SimpleUploadedFile('profile.gif', VALID_GIF_BYTES, content_type='image/gif'),
        }

        response = self.client.post(reverse('employee:offline_application_create'), payload)

        student_user = User.objects.get(username='asha.uploads@example.com')
        student_profile = StudentProfile.objects.get(user=student_user)
        portal_application = Application.objects.get(student=student_user)
        supplemental_profile = ApplicationSupplementalProfile.objects.get(application=portal_application)

        self.assertRedirects(
            response,
            reverse('employee:student_application_detail', kwargs={'application_id': portal_application.id}),
            fetch_redirect_response=False,
        )
        self.assertTrue(student_profile.profile_picture.name)
    def test_employee_can_create_partial_offline_application_without_core_details(self):
        self.client.login(username='employee@example.com', password='EmployeePass123!')

        response = self.client.post(
            reverse('employee:offline_application_create'),
            {
                'preferred_program_1': 'Computer Science',
            },
        )

        offline_application = StudentApplication.objects.get()
        student_user = offline_application.student_user
        portal_application = offline_application.portal_application
        student_profile = StudentProfile.objects.get(user=student_user)

        self.assertRedirects(
            response,
            reverse('employee:student_application_detail', kwargs={'application_id': portal_application.id}),
            fetch_redirect_response=False,
        )
        self.assertTrue(student_user.username.startswith('offline-student-'))
        self.assertEqual(student_user.email, '')
        self.assertEqual(offline_application.full_name, '')
        self.assertEqual(offline_application.email, '')
        self.assertEqual(offline_application.phone, '')
        self.assertEqual(student_profile.preferred_program_1, 'Computer Science')
        self.assertEqual(student_profile.olevel_school_country, '')
        self.assertTrue(offline_application.account_created)


class PortalUpdateMultiUploadTests(TestCase):
    def setUp(self):
        self.temp_media_root = tempfile.mkdtemp()
        self.storage_settings = override_settings(
            MEDIA_ROOT=self.temp_media_root,
            SECURE_SSL_REDIRECT=False,
            STORAGES=TEST_FILE_STORAGES,
        )
        self.storage_settings.enable()

    def tearDown(self):
        self.storage_settings.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)

    def test_gallery_images_and_attachments_accept_multiple_files(self):
        form = PortalUpdateForm(
            data={
                'content_type': 'blog',
                'title': 'Campus Update',
                'excerpt': 'Short summary',
                'content': 'Full content',
                'status': 'draft',
            },
            files={
                'gallery_images': [
                    SimpleUploadedFile('photo1.jpg', b'filecontent1', content_type='image/jpeg'),
                    SimpleUploadedFile('photo2.jpg', b'filecontent2', content_type='image/jpeg'),
                ],
                'attachments': [
                    SimpleUploadedFile('file1.pdf', b'pdfcontent1', content_type='application/pdf'),
                    SimpleUploadedFile('file2.pdf', b'pdfcontent2', content_type='application/pdf'),
                ],
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        update = form.save()
        form.save_related_files(update)

        self.assertEqual(PortalUpdate.objects.count(), 1)
        self.assertEqual(update.gallery_images.count(), 2)
        self.assertEqual(update.attachments.count(), 2)

    def test_pdf_attachment_keeps_original_file_content_and_name(self):
        pdf_bytes = b'%PDF-1.4 preserved pdf bytes'
        form = PortalUpdateForm(
            data={
                'content_type': 'blog',
                'title': 'Downloadable Guide',
                'excerpt': 'Short summary',
                'content': 'Full content',
                'status': 'draft',
            },
            files={
                'attachments': [
                    SimpleUploadedFile(
                        'guide.pdf',
                        pdf_bytes,
                        content_type='application/pdf',
                    ),
                ],
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        update = form.save()
        form.save_related_files(update)

        attachment = update.attachments.get()
        self.assertEqual(attachment.title, 'guide.pdf')
        self.assertTrue(attachment.file.name.endswith('.pdf'))
        attachment.file.open('rb')
        self.assertEqual(attachment.file.read(), pdf_bytes)

    def test_published_update_attachment_downloads_original_file(self):
        pdf_bytes = b'%PDF-1.4 public download bytes'
        update = PortalUpdate.objects.create(
            content_type='blog',
            title='Published Guide',
            excerpt='Short summary',
            content='Full content',
            status='published',
        )
        attachment = PortalUpdateAttachment.objects.create(
            update=update,
            file=SimpleUploadedFile(
                'published-guide.pdf',
                pdf_bytes,
                content_type='application/pdf',
            ),
            title='published-guide.pdf',
        )

        response = self.client.get(
            reverse(
                'global_agency:update_attachment_download',
                args=[update.slug, attachment.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('published-guide.pdf', response['Content-Disposition'])
        self.assertEqual(b''.join(response.streaming_content), pdf_bytes)

    def test_draft_update_attachment_is_not_publicly_downloadable(self):
        update = PortalUpdate.objects.create(
            content_type='blog',
            title='Draft Guide',
            excerpt='Short summary',
            content='Full content',
            status='draft',
        )
        attachment = PortalUpdateAttachment.objects.create(
            update=update,
            file=SimpleUploadedFile(
                'draft-guide.pdf',
                b'%PDF-1.4 draft bytes',
                content_type='application/pdf',
            ),
            title='draft-guide.pdf',
        )

        response = self.client.get(
            reverse(
                'global_agency:update_attachment_download',
                args=[update.slug, attachment.id],
            )
        )

        self.assertEqual(response.status_code, 404)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES=TEST_FILE_STORAGES,
)
class PartnerPortalTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='employee.reviewer@example.com',
            email='employee.reviewer@example.com',
            password='EmployeePass123!',
            first_name='Reviewer',
            last_name='Staff',
        )
        UserProfile.objects.create(
            user=self.employee_user,
            role='employee',
            registration_method='admin',
        )

        self.partner_payload = {
            'full_name': 'Grace Mushi',
            'email': 'partner@example.com',
            'password': 'PartnerPass123!',
            'confirm_password': 'PartnerPass123!',
            'terms_accepted': True,
        }
        self.student_payload = {
            'full_name': 'Amina Juma',
            'gender': 'female',
            'nationality': 'Tanzanian',
            'email': 'amina@example.com',
            'phone': '255712345678',
            'address': 'Mwanza, Tanzania',
            'olevel_school': 'Mwanza Secondary School',
            'olevel_school_country': 'Tanzania',
            'olevel_school_region': 'Mwanza',
            'olevel_completed_year': '2022',
            'olevel_candidate_no': 'S1234/2022/0001',
            'olevel_gpa': 'Division I',
            'preferred_country_1': 'Canada',
            'preferred_program_1': 'Computer Science',
            'emergency_name': 'Neema Juma',
            'emergency_occupation': 'Teacher',
            'emergency_gender': 'female',
            'emergency_relation': 'Mother',
            'heard_about_us': 'Referral',
        }

    def test_partner_registration_requires_email_activation(self):
        response = self.client.post(reverse('employee:partner_register'), self.partner_payload)

        partner_user = User.objects.get(username='partner@example.com')
        partner_profile = partner_user.userprofile
        activation_url = reverse(
            'employee:partner_activate',
            kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(partner_user.pk)),
                'token': default_token_generator.make_token(partner_user),
            },
        )

        self.assertRedirects(response, reverse('employee:partner_login'), fetch_redirect_response=False)
        self.assertFalse(partner_user.is_active)
        self.assertEqual(partner_profile.role, 'partner')
        self.assertEqual(partner_profile.registration_method, 'partner')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/employee/partners/activate/', mail.outbox[0].body)

        activation_response = self.client.get(activation_url)
        self.assertRedirects(activation_response, reverse('employee:partner_login'), fetch_redirect_response=False)
        partner_user.refresh_from_db()
        self.assertTrue(partner_user.is_active)
        self.assertFalse(partner_profile.is_partner_approved)

    def test_partner_must_wait_for_employee_approval_after_email_activation(self):
        self.client.post(reverse('employee:partner_register'), self.partner_payload)
        partner_user = User.objects.get(username='partner@example.com')
        activation_url = reverse(
            'employee:partner_activate',
            kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(partner_user.pk)),
                'token': default_token_generator.make_token(partner_user),
            },
        )
        self.client.get(activation_url)

        response = self.client.post(
            reverse('employee:partner_login'),
            {'username': 'partner@example.com', 'password': 'PartnerPass123!'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'waiting for employee approval')

    def _activate_and_approve_partner(self):
        self.client.post(reverse('employee:partner_register'), self.partner_payload)
        partner_user = User.objects.get(username='partner@example.com')
        activation_url = reverse(
            'employee:partner_activate',
            kwargs={
                'uidb64': urlsafe_base64_encode(force_bytes(partner_user.pk)),
                'token': default_token_generator.make_token(partner_user),
            },
        )
        self.client.get(activation_url)
        self.client.login(username='employee.reviewer@example.com', password='EmployeePass123!')
        approval_response = self.client.post(
            reverse('employee:approve_partner_account', kwargs={'profile_id': partner_user.userprofile.id})
        )
        self.assertRedirects(approval_response, reverse('employee:employee_dashboard'), fetch_redirect_response=False)
        self.client.logout()
        self.client.login(username='partner@example.com', password='PartnerPass123!')
        partner_user.refresh_from_db()
        self.assertTrue(partner_user.userprofile.is_partner_approved)
        return partner_user

    def test_partner_can_create_owned_student_record(self):
        partner_user = self._activate_and_approve_partner()

        response = self.client.post(reverse('employee:partner_application_create'), self.student_payload)

        self.assertRedirects(response, reverse('employee:partner_dashboard'), fetch_redirect_response=False)
        application = StudentApplication.objects.get(email='amina@example.com')
        self.assertEqual(application.created_by, partner_user)
        self.assertTrue(application.account_created)
        self.assertIsNotNone(application.portal_application)
        self.assertEqual(application.student_user.username, 'amina@example.com')

    def test_partner_parent_mode_allows_missing_parent_details(self):
        self._activate_and_approve_partner()

        partial_payload = self.student_payload.copy()
        partial_payload.update(
            {
                'parent_entry_mode': 'parents',
                'father_name': '',
                'mother_name': '',
                'emergency_name': '',
                'emergency_relation': '',
                'emergency_gender': '',
            }
        )

        response = self.client.post(reverse('employee:partner_application_create'), partial_payload)

        self.assertRedirects(response, reverse('employee:partner_dashboard'), fetch_redirect_response=False)
        application = StudentApplication.objects.get(email='amina@example.com')
        self.assertFalse(application.father_name)
        self.assertFalse(application.mother_name)
        self.assertFalse(application.emergency_name)

    def test_employee_review_pages_show_partner_submission_context(self):
        self._activate_and_approve_partner()
        self.client.post(reverse('employee:partner_application_create'), self.student_payload)

        portal_application = Application.objects.get(student__username='amina@example.com')

        self.client.logout()
        self.client.login(username='employee.reviewer@example.com', password='EmployeePass123!')

        list_response = self.client.get(reverse('employee:student_application_list'))
        detail_response = self.client.get(
            reverse('employee:student_application_detail', kwargs={'application_id': portal_application.id})
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'Partner Entry')
        self.assertContains(list_response, 'Grace Mushi')

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Partner Submitted Application')
        self.assertContains(detail_response, 'Grace Mushi')

    def test_partner_entered_profile_completion_is_computed_accurately(self):
        self._activate_and_approve_partner()
        self.client.post(reverse('employee:partner_application_create'), self.student_payload)

        portal_application = Application.objects.get(student__username='amina@example.com')
        student_profile = StudentProfile.objects.get(user=portal_application.student)

        completion = student_profile.get_completion_status()
        self.assertEqual(completion['percentage'], 100)
        self.assertTrue(completion['personal_details_complete'])
        self.assertTrue(completion['parents_details_complete'])
        self.assertTrue(completion['academic_qualifications_complete'])
        self.assertTrue(completion['study_preferences_complete'])
        self.assertTrue(completion['emergency_contact_complete'])

        self.client.logout()
        self.client.login(username='employee.reviewer@example.com', password='EmployeePass123!')
        detail_response = self.client.get(
            reverse('employee:student_application_detail', kwargs={'application_id': portal_application.id})
        )
        self.assertContains(detail_response, '100%')

    def test_employee_can_export_partner_entry_using_csc_style_pdf(self):
        self._activate_and_approve_partner()
        self.client.post(reverse('employee:partner_application_create'), self.student_payload)

        portal_application = Application.objects.get(student__username='amina@example.com')

        self.client.logout()
        self.client.login(username='employee.reviewer@example.com', password='EmployeePass123!')
        response = self.client.get(
            reverse('employee:export_single_application_pdf', kwargs={'application_id': portal_application.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_partner_can_upload_student_image_and_supplemental_fields(self):
        self._activate_and_approve_partner()

        payload = self.student_payload.copy()
        payload.update(
            {
                'surname': 'Juma',
                'given_name': 'Amina',
                'passport_number': 'TZ1234567',
                'native_language': 'Swahili',
                'personal_email': 'amina.personal@example.com',
                'highest_education_level': 'Advanced Level',
                'highest_education_country': 'Tanzania',
                'highest_education_institute': 'Mwanza Secondary School',
                'highest_education_qualification': 'ACSEE',
                'english_proficiency': 'Good',
                'apply_as': 'Undergraduate',
                'preferred_teaching_language': 'English',
                'declaration_agreed': 'true',
            }
        )
        payload['profile_picture_upload'] = SimpleUploadedFile('profile.gif', VALID_GIF_BYTES, content_type='image/gif')

        response = self.client.post(reverse('employee:partner_application_create'), payload)

        self.assertRedirects(response, reverse('employee:partner_dashboard'), fetch_redirect_response=False)
        portal_application = Application.objects.get(student__username='amina@example.com')
        student_profile = StudentProfile.objects.get(user=portal_application.student)
        supplemental_profile = ApplicationSupplementalProfile.objects.get(application=portal_application)

        self.assertTrue(student_profile.profile_picture.name)
        self.assertEqual(supplemental_profile.passport_number, 'TZ1234567')
        self.assertTrue(supplemental_profile.declaration_agreed)


# ---------------------------------------------------------------------------
# PDF Export Ã¢â‚¬â€œ All Form Fields Rendered
# ---------------------------------------------------------------------------

@override_settings(
    ALLOWED_HOSTS=['testserver'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SECURE_SSL_REDIRECT=False,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES=TEST_FILE_STORAGES,
)
class PDFExportAllFieldsTests(TestCase):
    """Ensure every form field value set on the models actually appears in the
    generated PDF export data dictionary and in the rendered PDF bytes.

    The OfflineStudentIntakeForm writes to three models:
      - StudentProfile          (personal, parents, education, preferences, emergency)
      - ApplicationSupplementalProfile (passport, address, higher-ed, finance, medical)
      - StudentApplication       (work experience, prof quals, declaration, office)

    During save the view also creates WorkExperience rows. The PDF export
    function ``application_to_awec_csc_style_data`` must read ALL of those
    fields and place them into the data dict. These tests populate every
    single model field with known, unique-ish sentinel values and then assert
    they are present in the output data dict and in the raw PDF bytes.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='export@example.com',
            email='export@example.com',
            password='ExportPass123!',
            first_name='Export',
            last_name='Student',
        )
        UserProfile.objects.create(
            user=self.user,
            role='employee',
            registration_method='admin',
        )

        self.portal_application = Application.objects.create(
            student=self.user,
            status='submitted',
            is_paid=True,
            payment_status='paid',
            reference_number='AWECO/INT/REG/TZ/DSM/20268001',
        )

        self.student_profile = StudentProfile.objects.create(
            user=self.user,
            phone_number='0712345678',
            email='export@example.com',
            date_of_birth=date(2000, 5, 15),
            place_of_birth='Mwanza',
            nationality='Tanzanian',
            native_language='Swahili',
            marital_status='single',
            gender='female',
            # Current / home location
            city='Dar es Salaam',
            region='Dar es Salaam',
            ward='Mbezi Beach',
            street='Mbezi Beach Road',
            mtaa='Mbezi',
            village='Mbezi Beach',
            house_no='14',
            # Father
            father_name='James Export',
            father_phone='0723456789',
            father_email='james.export@example.com',
            father_occupation='Engineer',
            father_country='Tanzania',
            father_region='Dar es Salaam',
            father_district='Kinondoni',
            father_ward='Mbezi Beach',
            father_street='Mbezi Beach Road',
            father_house_no='14',
            father_place_neighbourhood='Mbezi',
            father_region_post_code='14100',
            father_district_post_code='14128',
            father_ward_post_code='14129',
            father_status='Alive',
            father_relationship='Father',
            # Mother
            mother_name='Grace Export',
            mother_phone='0734567890',
            mother_email='grace.export@example.com',
            mother_occupation='Teacher',
            mother_country='Tanzania',
            mother_region='Mwanza',
            mother_district='Nyamagana',
            mother_ward='Mkolani',
            mother_street='Mkolani Road',
            mother_house_no='7',
            mother_place_neighbourhood='Mkolani',
            mother_region_post_code='31000',
            mother_district_post_code='31101',
            mother_ward_post_code='31102',
            mother_status='Alive',
            mother_relationship='Mother',
            # O-Level
            olevel_school='Mlimani Secondary',
            olevel_start_year='2016',
            olevel_completed_year='2019',
            olevel_candidate_no='S001/2019/0001',
            olevel_gpa='Division I',
            olevel_school_country='Tanzania',
            olevel_school_region='Mwanza',
            olevel_school_district='Nyamagana',
            olevel_school_ward='Mkolani',
            olevel_school_street='Mkolani Road',
            olevel_school_house_no='7',
            olevel_school_place_neighbourhood='Mkolani',
            olevel_school_region_post_code='31000',
            olevel_school_district_post_code='31101',
            olevel_school_ward_post_code='31102',
            olevel_school_type='Day',
            olevel_exam_board='NECTA',
            olevel_certificate_no='CERT-001',
            olevel_remarks='Good performance',
            # A-Level
            alevel_school='Jangwani Secondary',
            alevel_start_year='2020',
            alevel_completed_year='2022',
            alevel_candidate_no='S002/2022/0002',
            alevel_gpa='Division II',
            alevel_school_country='Tanzania',
            alevel_school_region='Dar es Salaam',
            alevel_school_district='Ilala',
            alevel_school_ward='Upanga',
            alevel_school_street='Upanga Road',
            alevel_school_house_no='21',
            alevel_school_place_neighbourhood='Upanga',
            alevel_school_region_post_code='14100',
            alevel_school_district_post_code='14110',
            alevel_school_ward_post_code='14111',
            alevel_school_type='Day',
            alevel_exam_board='NECTA',
            alevel_certificate_no='CERT-002',
            alevel_remarks='Excellent results',
            # Study preferences
            preferred_intake='September',
            preferred_country_1='Canada',
            preferred_country_2='United Kingdom',
            preferred_country_3='Australia',
            preferred_program_1='Computer Science',
            preferred_program_2='Data Science',
            preferred_program_3='Artificial Intelligence',
            # Emergency contact
            emergency_contact='Daniel Emergency',
            emergency_relation='Uncle',
            emergency_occupation='Doctor',
            emergency_phone='0745678901',
            emergency_email='daniel.emergency@example.com',
            emergency_alternative_phone='0756789012',
            emergency_country='Tanzania',
            emergency_region='Dar es Salaam',
            emergency_district='Kinondoni',
            emergency_ward='Kinondoni',
            emergency_street='Sinza Road',
            emergency_place_neighbourhood='Sinza',
            emergency_house_no='5',
            emergency_region_post_code='14100',
            emergency_district_post_code='14120',
            emergency_ward_post_code='14121',
            emergency_relationship_status='Married',
            emergency_remarks='Available 24/7',
            # Heard about us
            heard_about_us='Google Search',
            heard_about_other='',
        )

        self.supplemental_profile = ApplicationSupplementalProfile.objects.create(
            application=self.portal_application,
            # Identity / Passport
            full_name_passport='Export Student',
            place_of_birth='Mwanza City',
            passport_number='A00123456',
            passport_issue_country='Tanzania',
            passport_issue_date=date(2023, 1, 15),
            passport_expiration_date=date(2033, 1, 15),
            has_valid_visa=False,
            valid_visa_details='',
            residential_email='export.residential@example.com',
            # Current address
            current_country='Tanzania',
            current_region='Dar es Salaam',
            current_region_post_code='14100',
            current_city='Dar es Salaam',
            current_district='Kinondoni',
            current_district_post_code='14128',
            current_ward='Mbezi Beach',
            current_ward_post_code='14129',
            current_street='Mbezi Beach Road',
            current_mtaa='Mbezi',
            current_house_no='14',
            current_postal_code='14100',
            current_address='Plot 14, Mbezi Beach',
            current_address_status='Owner',
            current_nearest_landmark='Mbezi Mall',
            current_duration_at_address='5 years',
            current_address_remarks='Well accessible',
            # Permanent address
            permanent_country='Tanzania',
            permanent_region='Mwanza',
            permanent_region_post_code='31000',
            permanent_city='Mwanza',
            permanent_district='Nyamagana',
            permanent_district_post_code='31101',
            permanent_ward='Mkolani',
            permanent_ward_post_code='31102',
            permanent_street='Mkolani Road',
            permanent_mtaa='Mkolani',
            permanent_house_no='7',
            permanent_postal_code='31000',
            permanent_address='Plot 7, Mkolani',
            permanent_address_status='Owner',
            permanent_nearest_landmark='Mkolani Market',
            permanent_duration_at_address='10 years',
            permanent_address_remarks='Permanent residence',
            # Higher education - Certificate
            certificate_institution='Arusha Technical College',
            certificate_field_of_study='Information Technology',
            certificate_start_year='2019',
            certificate_completed_year='2020',
            certificate_gpa='3.5',
            # Higher education - Diploma
            diploma_institution='Dar es Salaam Institute of Technology',
            diploma_field_of_study='Computer Science',
            diploma_start_year='2020',
            diploma_completed_year='2022',
            diploma_gpa='3.8',
            # Higher education - Bachelor
            bachelor_institution='University of Dar es Salaam',
            bachelor_field_of_study='Software Engineering',
            bachelor_start_year='2022',
            bachelor_completed_year='2025',
            bachelor_gpa='4.0',
            # Higher education - Master
            master_institution='',
            master_field_of_study='',
            master_start_year='',
            master_completed_year='',
            master_gpa='',
            # Higher education - PhD
            phd_institution='',
            phd_field_of_study='',
            phd_start_year='',
            phd_completed_year='',
            phd_gpa='',
            # Professional qualifications (single legacy fields)
            professional_qualifications='AWS Certified Solutions Architect',
            professional_qualification_institution='Amazon Web Services',
            professional_qualification_country='United States',
            professional_qualification_start_date=date(2023, 3, 1),
            professional_qualification_completed_date=date(2023, 6, 30),
            professional_qualification_certificate_awarded=True,
            # English proficiency
            english_test_name='IELTS',
            english_test_institution='British Council',
            english_test_score='7.5',
            english_test_year='2024',
            english_is_primary_language=False,
            # Study preferences & finance
            program_level='bachelor',
            preferred_intake='September',
            accommodation_preference='university_dormitory',
            education_sponsor='Self',
            estimated_budget_usd='25000.00',
            scholarship_applied=True,
            scholarship_details='Merit-based scholarship at UDSM',
            # Medical
            has_medical_condition=False,
            medical_condition_details='',
            needs_special_assistance=False,
            special_assistance_details='',
            # Declaration
            declaration_agreed=True,
            serial_number='AWECO/INT/REG/TZ/DSM/20268001',
        )

        # Work experience (created by _create_or_update_student_portal_records)
        self.work1 = WorkExperience.objects.create(
            student=self.student_profile,
            company_name='Tanzania Tech Ltd',
            position='Junior Developer',
            location='Dar es Salaam',
            start_date=date(2023, 7, 1),
            end_date=date(2024, 12, 31),
            currently_working=False,
            country='Tanzania',
            region='Dar es Salaam',
            region_post_code='14100',
            district='Kinondoni',
            district_post_code='14128',
            ward='Masaki',
            ward_post_code='14130',
            street='Masaki Road',
            neighbourhood='Masaki',
            house_no='3',
            employment_type='Full-time',
            supervisor='Mr. Manager',
            remarks='Good performance',
        )
        self.work2 = WorkExperience.objects.create(
            student=self.student_profile,
            company_name='East Africa Solutions',
            position='Intern',
            location='Mwanza',
            start_date=date(2022, 1, 1),
            end_date=date(2022, 6, 30),
            currently_working=False,
            country='Tanzania',
            region='Mwanza',
            region_post_code='31000',
            district='Nyamagana',
            district_post_code='31101',
            ward='Mkolani',
            ward_post_code='31102',
            street='Mkolani Road',
            neighbourhood='Mkolani',
            house_no='7',
            employment_type='Part-time',
            supervisor='Ms. Supervisor',
            remarks='Learned basics',
        )

    def _build_data(self):
        """Helper: build the PDF data dict from the test fixtures."""
        return application_to_awec_csc_style_data(
            self.portal_application,
            self.student_profile,
            self.supplemental_profile,
        )

    # -----------------------------------------------------------------
    # SECTION 1: Personal details fields
    # -----------------------------------------------------------------

    def test_personal_full_name_passport_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Full Name (as in passport)'], 'Export Student')

    def test_personal_gender_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Gender'], 'Female')

    def test_personal_date_of_birth_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Date of Birth'], '15/05/2000')

    def test_personal_place_of_birth_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Place of Birth'], 'Mwanza City')

    def test_personal_nationality_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Nationality'], 'Tanzanian')

    def test_personal_native_language_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Native Language'], 'Swahili')

    def test_personal_marital_status_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Marital Status'], 'single')

    def test_personal_city_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['City'], 'Dar es Salaam')

    def test_personal_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Region'], 'Dar es Salaam')

    def test_personal_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Ward'], 'Mbezi Beach')

    def test_personal_village_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Village'], 'Mbezi Beach')

    def test_personal_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Street'], 'Mbezi Beach Road')

    def test_personal_house_number_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['House Number'], '14')

    def test_personal_email_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Email'], 'export@example.com')

    def test_personal_phone_number_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Phone Number'], '0712345678')

    def test_personal_passport_number_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Passport Number'], 'A00123456')

    def test_personal_passport_issued_date_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Passport Issued Date'], '15/01/2023')

    def test_personal_passport_expired_date_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['Passport Expired Date'], '15/01/2033')

    def test_personal_application_id_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['meta']['application_id'], 'AWECO/INT/REG/TZ/DSM/20268001')

    # -----------------------------------------------------------------
    # SECTION 2: Parents details fields
    # -----------------------------------------------------------------

    def test_father_full_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Full Name'], 'James Export')

    def test_father_occupation_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Occupation'], 'Engineer')

    def test_father_phone_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Phone'], '0723456789')

    def test_father_email_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Email'], 'james.export@example.com')

    def test_father_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Country'], 'Tanzania')

    def test_father_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Region'], 'Dar es Salaam')

    def test_father_region_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Region Post Code'], '14100')

    def test_father_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['District'], 'Kinondoni')

    def test_father_district_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['District Post Code'], '14128')

    def test_father_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Ward'], 'Mbezi Beach')

    def test_father_ward_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Ward Post Code'], '14129')

    def test_father_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Street'], 'Mbezi Beach Road')

    def test_father_place_neighbourhood_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Place / Neighbourhood'], 'Mbezi')

    def test_father_house_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['House No.'], '14')

    def test_father_status_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Status'], 'Alive')

    def test_father_relationship_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Father']['Relationship'], 'Father')

    def test_mother_full_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Full Name'], 'Grace Export')

    def test_mother_occupation_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Occupation'], 'Teacher')

    def test_mother_phone_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Phone'], '0734567890')

    def test_mother_email_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Email'], 'grace.export@example.com')

    def test_mother_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Region'], 'Mwanza')

    def test_mother_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['District'], 'Nyamagana')

    def test_mother_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Ward'], 'Mkolani')

    def test_mother_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Street'], 'Mkolani Road')

    def test_mother_house_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['House No.'], '7')

    def test_mother_status_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Status'], 'Alive')

    def test_mother_relationship_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['parents']['Mother']['Relationship'], 'Mother')

    # -----------------------------------------------------------------
    # SECTION 3: Emergency contact details
    # -----------------------------------------------------------------

    def test_emergency_full_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Full Name'], 'Daniel Emergency')

    def test_emergency_relationship_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Relationship'], 'Uncle')

    def test_emergency_occupation_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Occupation'], 'Doctor')

    def test_emergency_phone_number_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Phone Number'], '0745678901')

    def test_emergency_email_address_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Email Address'], 'daniel.emergency@example.com')

    def test_emergency_alternative_phone_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Alternative Phone'], '0756789012')

    def test_emergency_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Country'], 'Tanzania')

    def test_emergency_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Region'], 'Dar es Salaam')

    def test_emergency_region_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Region Post Code'], '14100')

    def test_emergency_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['District'], 'Kinondoni')

    def test_emergency_district_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['District Post Code'], '14120')

    def test_emergency_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Ward'], 'Kinondoni')

    def test_emergency_ward_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Ward Post Code'], '14121')

    def test_emergency_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Street'], 'Sinza Road')

    def test_emergency_place_neighbourhood_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Place / Neighbourhood'], 'Sinza')

    def test_emergency_house_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['House No.'], '5')

    def test_emergency_relationship_status_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Relationship Status'], 'Married')

    def test_emergency_remarks_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['emergency']['Remarks'], 'Available 24/7')

    # -----------------------------------------------------------------
    # SECTION 4: Education background
    # -----------------------------------------------------------------

    def test_olevel_school_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['School Name'], 'Mlimani Secondary')

    def test_olevel_index_number_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Index Number'], 'S001/2019/0001')

    def test_olevel_start_year_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Start Year'], '2016')

    def test_olevel_completed_year_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Completed Year'], '2019')

    def test_olevel_division_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Division'], 'Division I')

    def test_olevel_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Country'], 'Tanzania')

    def test_olevel_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Region'], 'Mwanza')

    def test_olevel_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['District'], 'Nyamagana')

    def test_olevel_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Ward'], 'Mkolani')

    def test_olevel_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Street'], 'Mkolani Road')

    def test_olevel_school_type_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['School Type'], 'Day')

    def test_olevel_exam_board_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Exam Board'], 'NECTA')

    def test_olevel_certificate_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Certificate No.'], 'CERT-001')

    def test_olevel_remarks_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][0]['Remarks'], 'Good performance')

    def test_alevel_school_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['School Name'], 'Jangwani Secondary')

    def test_alevel_index_number_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['Index Number'], 'S002/2022/0002')

    def test_alevel_division_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['Division'], 'Division II')

    def test_alevel_school_type_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['School Type'], 'Day')

    def test_alevel_exam_board_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['Exam Board'], 'NECTA')

    def test_alevel_certificate_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['Certificate No.'], 'CERT-002')

    def test_alevel_remarks_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['education_background'][1]['Remarks'], 'Excellent results')

    # -----------------------------------------------------------------
    # Higher education
    # -----------------------------------------------------------------

    def test_certificate_institution_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][0]['Institution'], 'Arusha Technical College')

    def test_certificate_field_of_study_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][0]['Field of Study'], 'Information Technology')

    def test_certificate_start_year_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][0]['Start Year'], '2019')

    def test_certificate_completed_year_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][0]['Completed Year'], '2020')

    def test_certificate_gpa_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][0]['GPA'], '3.5')

    def test_diploma_institution_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][1]['Institution'], 'Dar es Salaam Institute of Technology')

    def test_diploma_field_of_study_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][1]['Field of Study'], 'Computer Science')

    def test_diploma_gpa_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][1]['GPA'], '3.8')

    def test_bachelor_institution_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][2]['Institution'], 'University of Dar es Salaam')

    def test_bachelor_field_of_study_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][2]['Field of Study'], 'Software Engineering')

    def test_bachelor_gpa_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['higher_education'][2]['GPA'], '4.0')

    def test_all_five_higher_education_levels_present(self):
        data = self._build_data()
        self.assertEqual(len(data['higher_education']), 5)
        expected_levels = ['Certificate', 'Diploma', 'Bachelor Degree', 'Master Degree', 'PhD']
        for i, level in enumerate(expected_levels):
            self.assertEqual(data['higher_education'][i]['Level'], level)

    # -----------------------------------------------------------------
    # Professional qualifications
    # -----------------------------------------------------------------

    def test_professional_qualifications_text_appears_in_export(self):
        data = self._build_data()
        self.assertIn('AWS Certified Solutions Architect',
                      data['professional_qualifications'][0]['Qualification Title'])

    def test_professional_qualification_institution_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['professional_qualifications'][0]['Institution'], 'Amazon Web Services')

    def test_professional_qualification_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['professional_qualifications'][0]['Country'], 'United States')

    def test_professional_qualification_start_date_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['professional_qualifications'][0]['Start Date'], '01/03/2023')

    def test_professional_qualification_finished_date_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['professional_qualifications'][0]['Finished Date'], '30/06/2023')

    # -----------------------------------------------------------------
    # English language proficiency
    # -----------------------------------------------------------------

    def test_english_test_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['english_proficiency']['Test Name'], 'IELTS')

    def test_english_test_institution_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['english_proficiency']['Institution'], 'British Council')

    def test_english_test_score_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['english_proficiency']['Score'], '7.5')

    def test_english_test_year_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['english_proficiency']['Year'], '2024')

    def test_english_is_primary_language_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['english_proficiency']['English is Primary Language?'], 'No')

    # -----------------------------------------------------------------
    # Employment history / Work experience
    # -----------------------------------------------------------------

    def test_work_experience_count_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(len(data['employment_history']), 2)

    def test_work1_employer_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Employer / Company Name'], 'Tanzania Tech Ltd')

    def test_work1_position_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Position / Job Title'], 'Junior Developer')

    def test_work1_start_date_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Start Date'], '01/07/2023')

    def test_work1_end_date_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['End Date'], '31/12/2024')

    def test_work1_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Country'], 'Tanzania')

    def test_work1_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Region'], 'Dar es Salaam')

    def test_work1_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['District'], 'Kinondoni')

    def test_work1_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Ward'], 'Masaki')

    def test_work1_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['Street'], 'Masaki Road')

    def test_work1_house_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][0]['House No.'], '3')

    def test_work2_employer_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][1]['Employer / Company Name'], 'East Africa Solutions')

    def test_work2_position_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['employment_history'][1]['Position / Job Title'], 'Intern')

    # -----------------------------------------------------------------
    # SECTION 6: Study preferences
    # -----------------------------------------------------------------

    def test_study_pref_preferred_intake_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Intake'], 'September')

    def test_study_pref_country1_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Country 1'], 'Canada')

    def test_study_pref_program1_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Program 1'], 'Computer Science')

    def test_study_pref_country2_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Country 2'], 'United Kingdom')

    def test_study_pref_program2_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Program 2'], 'Data Science')

    def test_study_pref_country3_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Country 3'], 'Australia')

    def test_study_pref_program3_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['study_preferences']['Preferred Program 3'], 'Artificial Intelligence')

    # -----------------------------------------------------------------
    # SECTION 7: Current and permanent address
    # -----------------------------------------------------------------

    def test_current_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Country'], 'Tanzania')

    def test_current_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Region'], 'Dar es Salaam')

    def test_current_region_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Region Post Code'], '14100')

    def test_current_city_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['personal']['City'], 'Dar es Salaam')

    def test_current_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current District'], 'Kinondoni')

    def test_current_district_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current District Post Code'], '14128')

    def test_current_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Ward'], 'Mbezi Beach')

    def test_current_ward_post_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Ward Post Code'], '14129')

    def test_current_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Street'], 'Mbezi Beach Road')

    def test_current_house_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current House No.'], '14')

    def test_current_postal_code_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Postal Code'], '14100')

    def test_current_address_status_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Address Status'], 'Owner')

    def test_current_nearest_landmark_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Nearest Landmark'], 'Mbezi Mall')

    def test_current_duration_at_address_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Duration at Address'], '5 years')

    def test_current_address_remarks_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Current Remarks'], 'Well accessible')

    def test_permanent_country_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Country'], 'Tanzania')

    def test_permanent_region_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Region'], 'Mwanza')

    def test_permanent_district_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent District'], 'Nyamagana')

    def test_permanent_ward_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Ward'], 'Mkolani')

    def test_permanent_street_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Street'], 'Mkolani Road')

    def test_permanent_house_no_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent House No.'], '7')

    def test_permanent_address_status_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Address Status'], 'Owner')

    def test_permanent_nearest_landmark_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Nearest Landmark'], 'Mkolani Market')

    def test_permanent_duration_at_address_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['addresses']['Permanent Duration at Address'], '10 years')

    # -----------------------------------------------------------------
    # SECTION 8: Other details
    # -----------------------------------------------------------------

    def test_valid_visa_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Valid Visa?'], 'No')

    def test_program_level_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Program Level'], 'Bachelor Degree')

    def test_accommodation_preference_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Accommodation Preference'], 'University Dormitory')

    def test_education_sponsor_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Sponsor of Education'], 'Self')

    def test_estimated_budget_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Estimated Budget (USD)'], '25,000.00')

    def test_scholarship_applied_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Scholarship Applied?'], 'Yes')

    def test_scholarship_details_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Scholarship Details (if applicable)'],
                         'Merit-based scholarship at UDSM')

    def test_medical_condition_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Any Medical Condition?'], 'No')

    def test_special_assistance_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['other_details']['Special Assistance Required?'], 'No')

    # -----------------------------------------------------------------
    # SECTION 9: How did you hear about us
    # -----------------------------------------------------------------

    def test_heard_about_us_source_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['heard_about_us']['Source'], 'Google Search')

    # -----------------------------------------------------------------
    # SECTION 10: Declaration
    # -----------------------------------------------------------------

    def test_declaration_full_name_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['declaration']['Applicant Full Name'], 'Export Student')

    def test_declaration_agreed_appears_in_export(self):
        data = self._build_data()
        self.assertEqual(data['declaration']['Declaration Agreed'], 'Yes')

    def test_declaration_date_is_today(self):
        data = self._build_data()
        self.assertEqual(data['declaration']['Date'], date.today().strftime('%d/%m/%Y'))

    # -----------------------------------------------------------------
    # PDF generation doesn't crash with all fields populated
    # -----------------------------------------------------------------

    def test_full_pdf_generation_succeeds(self):
        """The generate_pdf function must not raise when all fields are populated."""
        data = self._build_data()
        buf = BytesIO()
        generate_pdf(buf, data)
        pdf_bytes = buf.getvalue()
        buf.close()
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))
        self.assertGreater(len(pdf_bytes), 1000)

    def test_pdf_contains_all_key_values_in_bytes(self):
        """Verify the rendered PDF text contains sentinel field values."""
        import pypdf
        data = self._build_data()
        buf = BytesIO()
        generate_pdf(buf, data)
        buf.seek(0)
        reader = pypdf.PdfReader(buf)
        pdf_text = ''
        for page in reader.pages:
            pdf_text += page.extract_text() or ''
        buf.close()
        pdf_text_upper = pdf_text.upper()

        # Spot-check a representative field value from each major section
        expected_values = [
            # Personal
            'EXPORT STUDENT',
            'TANZANIAN',
            'SWAHILI',
            '0712345678',
            'A00123456',
            # Parents
            'JAMES EXPORT',
            'GRACE EXPORT',
            'ENGINEER',
            'TEACHER',
            # Emergency
            'DANIEL EMERGENCY',
            'UNCLE',
            '0745678901',
            # O-Level
            'MLIMANI SECONDARY',
            'S001/2019/0001',
            'DIVISION I',
            'NECTA',
            'CERT-001',
            # A-Level
            'JANGWANI SECONDARY',
            'S002/2022/0002',
            'DIVISION II',
            # Higher education
            'ARUSHA TECHNICAL COLLEGE',
            'UNIVERSITY OF DAR ES SALAAM',
            'SOFTWARE ENGINEERING',
            # Professional qualifications
            'AWS CERTIFIED',
            'AMAZON WEB SERVICES',
            # English
            'IELTS',
            'BRITISH COUNCIL',
            '7.5',
            # Work experience
            'TANZANIA TECH LTD',
            'JUNIOR DEVELOPER',
            'EAST AFRICA SOLUTIONS',
            # Study preferences
            'CANADA',
            'COMPUTER SCIENCE',
            'UNITED KINGDOM',
            'AUSTRALIA',
            # Addresses
            'DAR ES SALAAM',
            'MWANZA',
            'NYAMAGANA',
            # Other details
            'UNIVERSITY DORMITORY',
            # Heard about us
            'GOOGLE SEARCH',
            # Declaration
            'YES',
        ]
        for value in expected_values:
            self.assertIn(
                value.upper(),
                pdf_text_upper,
                f'Expected "{value}" in extracted PDF text but not found',
            )

    def test_all_expected_data_dict_keys_exist(self):
        """Every top-level section and expected sub-key must exist in the data dict."""
        data = self._build_data()

        # Personal keys
        expected_personal_keys = [
            'Full Name (as in passport)', 'Gender', 'Date of Birth',
            'Place of Birth', 'Nationality', 'Native Language',
            'Marital Status', 'City', 'Region', 'Ward', 'Village',
            'Street', 'House Number', 'Email', 'Phone Number',
            'Passport Number', 'Passport Issued Date', 'Passport Expired Date',
            'Application ID / Serial Number', 'Student Photo',
        ]
        for key in expected_personal_keys:
            self.assertIn(key, data['personal'], f'Missing personal key: {key}')

        # Parents keys
        for parent_key in ['Father', 'Mother']:
            self.assertIn(parent_key, data['parents'])
            for field in ['Full Name', 'Occupation', 'Phone', 'Email', 'Country',
                          'Region', 'District', 'Ward', 'Street', 'House No.',
                          'Status', 'Relationship']:
                self.assertIn(field, data['parents'][parent_key],
                              f'Missing {parent_key} key: {field}')

        # Emergency keys
        expected_emergency_keys = [
            'Full Name', 'Relationship', 'Occupation', 'Phone Number',
            'Email Address', 'Alternative Phone', 'Country', 'Region',
            'District', 'Ward', 'Street', 'House No.',
            'Relationship Status', 'Remarks',
        ]
        for key in expected_emergency_keys:
            self.assertIn(key, data['emergency'], f'Missing emergency key: {key}')

        # Education keys
        self.assertEqual(len(data['education_background']), 2)
        for edu in data['education_background']:
            for field in ['Level', 'School Name', 'Index Number', 'Start Year',
                          'Completed Year', 'Division', 'School Type', 'Exam Board',
                          'Certificate No.', 'Remarks']:
                self.assertIn(field, edu, f'Missing education key: {field}')

        # Higher education - 5 levels
        self.assertEqual(len(data['higher_education']), 5)
        for he in data['higher_education']:
            for field in ['Level', 'Institution', 'Field of Study', 'Start Year',
                          'Completed Year', 'GPA']:
                self.assertIn(field, he, f'Missing higher education key: {field}')

        # Professional qualifications - 3 entries
        self.assertEqual(len(data['professional_qualifications']), 3)
        for pq in data['professional_qualifications']:
            for field in ['Qualification Title', 'Institution', 'Country',
                          'Start Date', 'Finished Date']:
                self.assertIn(field, pq, f'Missing prof qual key: {field}')

        # English proficiency
        for field in ['Test Name', 'Institution', 'Score', 'Year',
                      'English is Primary Language?']:
            self.assertIn(field, data['english_proficiency'],
                          f'Missing english key: {field}')

        # Study preferences
        for field in ['Preferred Intake', 'Preferred Country 1', 'Preferred Program 1',
                      'Preferred Country 2', 'Preferred Program 2',
                      'Preferred Country 3', 'Preferred Program 3']:
            self.assertIn(field, data['study_preferences'],
                          f'Missing study pref key: {field}')

        # Addresses
        for field in ['Current Country', 'Current Region', 'Current District',
                      'Current Ward', 'Current Street', 'Current House No.',
                      'Current Postal Code', 'Current Address Status',
                      'Current Nearest Landmark', 'Current Duration at Address',
                      'Permanent Country', 'Permanent Region', 'Permanent District',
                      'Permanent Ward', 'Permanent Street', 'Permanent House No.',
                      'Permanent Address Status', 'Permanent Nearest Landmark',
                      'Permanent Duration at Address']:
            self.assertIn(field, data['addresses'], f'Missing address key: {field}')

        # Other details
        for field in ['Valid Visa?', 'Program Level', 'Accommodation Preference',
                      'Sponsor of Education', 'Estimated Budget (USD)',
                      'Scholarship Applied?', 'Scholarship Details (if applicable)',
                      'Any Medical Condition?', 'Special Assistance Required?']:
            self.assertIn(field, data['other_details'],
                          f'Missing other details key: {field}')

        # Heard about us
        self.assertIn('Source', data['heard_about_us'])
        self.assertIn('Other (please specify)', data['heard_about_us'])

        # Declaration
        for field in ['Applicant Full Name', 'Date', 'Signature', 'Declaration Agreed']:
            self.assertIn(field, data['declaration'], f'Missing declaration key: {field}')

    # -----------------------------------------------------------------
    # HTTP endpoint test
    # -----------------------------------------------------------------

    def test_export_pdf_view_returns_valid_pdf_with_all_fields(self):
        """The employee export endpoint must return a valid PDF when all
        model fields are populated."""
        import pypdf
        self.client.login(username='export@example.com', password='ExportPass123!')
        response = self.client.get(
            reverse('employee:export_single_application_pdf',
                    kwargs={'application_id': self.portal_application.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        # Extract text from the PDF to verify sentinel values
        buf = BytesIO(response.content)
        reader = pypdf.PdfReader(buf)
        pdf_text = ''
        for page in reader.pages:
            pdf_text += (page.extract_text() or '').upper()
        buf.close()
        self.assertIn('EXPORT STUDENT', pdf_text)
        self.assertIn('TANZANIA TECH LTD', pdf_text)
        self.assertIn('AWS CERTIFIED', pdf_text)
        self.assertIn('IELTS', pdf_text)
        self.assertIn('CANADA', pdf_text)
        self.assertIn('JAMES EXPORT', pdf_text)
        self.assertIn('GRACE EXPORT', pdf_text)
        self.assertIn('DANIEL EMERGENCY', pdf_text)



# ---------------------------------------------------------------------------
# PDF Export - Attached Documents Section
# ---------------------------------------------------------------------------

@override_settings(
    ALLOWED_HOSTS=['testserver'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    MEDIA_ROOT=tempfile.mkdtemp(),
    STORAGES=TEST_FILE_STORAGES,
)
class ExportDocumentsTests(TestCase):
    """Tests that the exported PDF includes the student's attached documents."""

    def setUp(self):
        self.employee_user = User.objects.create_user(
            username='export-docs@example.com',
            email='export-docs@example.com',
            password='ExportPass123!',
            first_name='Export',
            last_name='Staff',
        )
        UserProfile.objects.create(
            user=self.employee_user,
            role='employee',
            registration_method='admin',
        )

        self.student_user = User.objects.create_user(
            username='docstudent@example.com',
            email='docstudent@example.com',
            password='StudentPass123!',
            first_name='Doc',
            last_name='Student',
        )

        self.portal_application = Application.objects.create(
            student=self.student_user,
            status='submitted',
            is_paid=True,
            payment_status='paid',
        )

        StudentProfile.objects.create(
            user=self.student_user,
            gender='male',
            nationality='Tanzanian',
            preferred_country_1='Canada',
            preferred_program_1='Computer Science',
        )

        self.supplemental_profile = ApplicationSupplementalProfile.objects.create(
            application=self.portal_application,
            passport_number='DOC123456',
            declaration_agreed=True,
        )

    def _export_pdf(self):
        self.client.login(username='export-docs@example.com', password='ExportPass123!')
        return self.client.get(
            reverse('employee:export_single_application_pdf',
                    kwargs={'application_id': self.portal_application.id})
        )

    def _extract_pdf_text(self, response):
        import pypdf
        buf = BytesIO(response.content)
        reader = pypdf.PdfReader(buf)
        text = ''
        for page in reader.pages:
            text += (page.extract_text() or '').upper()
        buf.close()
        return text

    def _build_data(self, documents=None):
        return application_to_awec_csc_style_data(
            self.portal_application,
            StudentProfile.objects.get(user=self.student_user),
            self.supplemental_profile,
            documents=documents,
        )

    def test_export_returns_valid_pdf(self):
        """The export endpoint must return a valid PDF."""
        response = self._export_pdf()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_documents_key_always_present_in_data_dict(self):
        """The data dictionary must always contain a 'documents' key."""
        data = self._build_data()
        self.assertIn('documents', data)
        self.assertIsInstance(data['documents'], list)

    def test_data_dict_includes_documents_when_provided(self):
        """When Document objects are passed, the data dict must include them."""
        doc = Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='Passport Copy',
            file=SimpleUploadedFile('passport.pdf', b'fake-content', content_type='application/pdf'),
            description='Passport bio page',
            is_verified=True,
        )
        data = self._build_data(documents=[doc])
        self.assertEqual(len(data['documents']), 1)
        d = data['documents'][0]
        self.assertEqual(d['Document Type'], 'Passport Copy')
        self.assertIn('passport.pdf', d['File Name'].lower())
        self.assertEqual(d['Description'], 'Passport bio page')
        self.assertEqual(d['Verified'], 'Yes')

    def test_data_dict_empty_when_no_documents(self):
        """When no documents exist, the data dict must have an empty list."""
        data = self._build_data(documents=[])
        self.assertEqual(data['documents'], [])

    def test_data_dict_multiple_documents(self):
        """Multiple documents must all appear in the data dict."""
        doc1 = Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='Passport Copy',
            file=SimpleUploadedFile('passport.pdf', b'fake', content_type='application/pdf'),
            description='Bio page',
            is_verified=True,
        )
        doc2 = Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='Degree Certificate',
            file=SimpleUploadedFile('degree.pdf', b'fake', content_type='application/pdf'),
            description='Bachelor cert',
            is_verified=False,
        )
        data = self._build_data(documents=[doc1, doc2])
        self.assertEqual(len(data['documents']), 2)
        types = {d['Document Type'] for d in data['documents']}
        self.assertEqual(types, {'Passport Copy', 'Degree Certificate'})
        verified = {d['Verified'] for d in data['documents']}
        self.assertEqual(verified, {'Yes', 'No'})

    def test_pdf_text_contains_documents_section(self):
        """The rendered PDF text must contain the ATTACHED DOCUMENTS section."""
        Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='Passport Copy',
            file=SimpleUploadedFile('passport.pdf', b'fake-content', content_type='application/pdf'),
            description='Passport bio page',
            is_verified=True,
        )
        response = self._export_pdf()
        pdf_text = self._extract_pdf_text(response)
        self.assertIn('ATTACHED DOCUMENTS', pdf_text)

    def test_pdf_text_shows_no_documents_notice(self):
        """When no documents exist, the PDF must show 'No documents attached'."""
        response = self._export_pdf()
        pdf_text = self._extract_pdf_text(response)
        self.assertIn('ATTACHED DOCUMENTS', pdf_text)
        self.assertIn('NO DOCUMENTS ATTACHED', pdf_text)

    def test_pdf_text_lists_document_types(self):
        """Document types and file names must appear in the rendered PDF."""
        Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='Passport Copy',
            file=SimpleUploadedFile('passport.pdf', b'fake', content_type='application/pdf'),
            description='Bio page scan',
            is_verified=True,
        )
        Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='Degree Certificate',
            file=SimpleUploadedFile('degree.pdf', b'fake', content_type='application/pdf'),
            description='Bachelor degree cert',
            is_verified=False,
        )
        response = self._export_pdf()
        pdf_text = self._extract_pdf_text(response)
        self.assertIn('PASSPORT COPY', pdf_text)
        self.assertIn('DEGREE CERTIFICATE', pdf_text)
        self.assertIn('BIO PAGE SCAN', pdf_text)
        self.assertIn('BACHELOR DEGREE CERT', pdf_text)
        self.assertIn('YES', pdf_text)
        self.assertIn('NO', pdf_text)

    def test_documents_from_other_student_excluded(self):
        """Documents from a different student must NOT appear in this export."""
        other_student = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='OtherPass123!',
        )
        Document.objects.create(
            student=other_student,
            document_type='CV',
            file=SimpleUploadedFile('cv.pdf', b'fake', content_type='application/pdf'),
            description='Other student CV',
        )
        my_doc = Document.objects.create(
            student=self.student_user,
            application=self.portal_application,
            document_type='CV',
            file=SimpleUploadedFile('my_cv.pdf', b'fake', content_type='application/pdf'),
            description='My CV',
        )
        data = self._build_data(documents=[my_doc])
        self.assertEqual(len(data['documents']), 1)
        self.assertIn('MY CV', data['documents'][0]['Description'].upper())
        self.assertNotIn('OTHER STUDENT', data['documents'][0]['Description'].upper())
