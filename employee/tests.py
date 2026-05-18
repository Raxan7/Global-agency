from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pathlib import Path
import shutil
import tempfile

from global_agency.models import ContactMessage, StudentApplication
from employee.forms import PortalUpdateForm
from employee.models import PortalUpdate, PortalUpdateAttachment, UserProfile
from student_portal.models import Application, ApplicationSupplementalProfile, Document, StudentProfile

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
            'profile_picture_upload': SimpleUploadedFile('profile.gif', VALID_GIF_BYTES, content_type='image/gif'),
            'passport_document': SimpleUploadedFile('passport.pdf', b'%PDF-1.4 employee passport', content_type='application/pdf'),
        }

        response = self.client.post(reverse('employee:offline_application_create'), payload)

        student_user = User.objects.get(username='asha.uploads@example.com')
        student_profile = StudentProfile.objects.get(user=student_user)
        portal_application = Application.objects.get(student=student_user)
        supplemental_profile = ApplicationSupplementalProfile.objects.get(application=portal_application)
        passport_documents = Document.objects.filter(student=student_user, document_type='passport')

        self.assertRedirects(
            response,
            reverse('employee:student_application_detail', kwargs={'application_id': portal_application.id}),
            fetch_redirect_response=False,
        )
        self.assertTrue(student_profile.profile_picture.name)
        self.assertEqual(passport_documents.count(), 1)
        self.assertTrue(passport_documents.first().file.name)
        self.assertTrue(supplemental_profile.has_passport_home_page)

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
        self.assertEqual(student_profile.olevel_country, 'Tanzania')
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
            'olevel_country': 'Tanzania',
            'olevel_address': 'Mwanza',
            'olevel_region': 'Mwanza',
            'olevel_year': '2022',
            'olevel_candidate_no': 'S1234/2022/0001',
            'olevel_gpa': 'Division I',
            'preferred_country_1': 'Canada',
            'preferred_program_1': 'Computer Science',
            'emergency_name': 'Neema Juma',
            'emergency_address': 'Mwanza, Tanzania',
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
                'emergency_address': '',
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

    def test_partner_can_upload_student_image_documents_and_supplemental_fields(self):
        self._activate_and_approve_partner()

        payload = self.student_payload.copy()
        payload.update(
            {
                'surname': 'Juma',
                'given_name': 'Amina',
                'passport_no': 'TZ1234567',
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
        payload['passport_document'] = SimpleUploadedFile('passport.pdf', b'pdfcontent', content_type='application/pdf')
        payload['academic_transcript_document'] = SimpleUploadedFile('transcript.pdf', b'pdfcontent', content_type='application/pdf')

        response = self.client.post(reverse('employee:partner_application_create'), payload)

        self.assertRedirects(response, reverse('employee:partner_dashboard'), fetch_redirect_response=False)
        portal_application = Application.objects.get(student__username='amina@example.com')
        student_profile = StudentProfile.objects.get(user=portal_application.student)
        supplemental_profile = ApplicationSupplementalProfile.objects.get(application=portal_application)
        documents = Document.objects.filter(student=portal_application.student)

        self.assertTrue(student_profile.profile_picture.name)
        self.assertEqual(supplemental_profile.passport_no, 'TZ1234567')
        self.assertEqual(supplemental_profile.highest_education_institute, 'Mwanza Secondary School')
        self.assertTrue(supplemental_profile.declaration_agreed)
        self.assertTrue(supplemental_profile.has_passport_photo)
        self.assertTrue(supplemental_profile.has_passport_home_page)
        self.assertTrue(supplemental_profile.has_highest_education_transcript)
        self.assertEqual(documents.count(), 2)

    def test_partner_edit_without_new_upload_keeps_existing_document(self):
        self._activate_and_approve_partner()

        create_payload = self.student_payload.copy()
        create_payload['passport_document'] = SimpleUploadedFile(
            'passport-initial.pdf',
            b'%PDF-1.4 initial passport',
            content_type='application/pdf',
        )
        self.client.post(reverse('employee:partner_application_create'), create_payload)

        application = StudentApplication.objects.get(email='amina@example.com')
        existing_document = Document.objects.get(student=application.student_user, document_type='passport')
        existing_name = existing_document.file.name

        response = self.client.post(
            reverse('employee:partner_application_edit', kwargs={'pk': application.id}),
            self.student_payload,
        )

        document_after_edit = Document.objects.get(student=application.student_user, document_type='passport')
        self.assertRedirects(response, reverse('employee:partner_dashboard'), fetch_redirect_response=False)
        self.assertEqual(Document.objects.filter(student=application.student_user, document_type='passport').count(), 1)
        self.assertEqual(document_after_edit.file.name, existing_name)

    def test_partner_edit_new_upload_replaces_existing_document_type(self):
        self._activate_and_approve_partner()

        create_payload = self.student_payload.copy()
        create_payload['passport_document'] = SimpleUploadedFile(
            'passport-initial.pdf',
            b'%PDF-1.4 initial passport',
            content_type='application/pdf',
        )
        self.client.post(reverse('employee:partner_application_create'), create_payload)

        application = StudentApplication.objects.get(email='amina@example.com')
        first_document = Document.objects.get(student=application.student_user, document_type='passport')
        first_name = first_document.file.name

        edit_payload = self.student_payload.copy()
        edit_payload['passport_document'] = SimpleUploadedFile(
            'passport-updated.pdf',
            b'%PDF-1.4 updated passport',
            content_type='application/pdf',
        )

        response = self.client.post(
            reverse('employee:partner_application_edit', kwargs={'pk': application.id}),
            edit_payload,
        )

        updated_document = Document.objects.get(student=application.student_user, document_type='passport')
        self.assertRedirects(response, reverse('employee:partner_dashboard'), fetch_redirect_response=False)
        self.assertEqual(Document.objects.filter(student=application.student_user, document_type='passport').count(), 1)
        self.assertTrue(updated_document.file.name)
        self.assertNotEqual(updated_document.file.name, first_name)
