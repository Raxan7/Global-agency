from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import (
    Application,
    ApplicationSupplementalAddress,
    ApplicationSupplementalProfile,
    StudentAddress,
    StudentFamilyContact,
    StudentPassport,
    StudentProfile,
    StudentSchoolHistory,
)


User = get_user_model()


class NormalizedSyncTests(TestCase):
    def _create_user(self, username='student@example.com'):
        return User.objects.create_user(
            username=username,
            email=username,
            first_name='Test',
            last_name='Student',
            password='secret123!',
        )

    def test_student_profile_sync_populates_address_and_passport(self):
        user = self._create_user()
        profile = StudentProfile.objects.create(
            user=user,
            father_name='John Doe',
            father_phone='+255700000001',
            father_country='Kenya',
            father_region='Dar es Salaam',
            father_district='Kinondoni',
            father_ward='Msasani',
            father_street='Bagamoyo Road',
            father_house_no='12',
            passport_number='A1234567',
            passport_issue_country='Tanzania',
            passport_issue_date='2020-01-15',
            passport_expiration_date='2030-01-15',
        )
        profile.sync_normalized_fields()
        self.assertEqual(StudentAddress.objects.filter(student=profile).count(), 1)
        father = profile.get_address('father')
        self.assertIsNotNone(father)
        self.assertEqual(father.country, 'Kenya')
        self.assertEqual(father.street, 'Bagamoyo Road')
        self.assertEqual(StudentPassport.objects.filter(student=profile).count(), 1)
        passport = profile.get_passport()
        self.assertIsNotNone(passport)
        self.assertEqual(passport.passport_number, 'A1234567')

    def test_family_contacts_and_school_history(self):
        user = self._create_user('student2@example.com')
        profile = StudentProfile.objects.create(
            user=user,
            mother_name='Jane Doe',
            mother_phone='+255700000002',
            olevel_school='Kibaha Secondary',
            olevel_school_country='Tanzania',
            olevel_completed_year='2020',
        )
        profile.sync_normalized_fields()
        self.assertEqual(StudentFamilyContact.objects.filter(student=profile).count(), 1)
        self.assertEqual(StudentSchoolHistory.objects.filter(student=profile).count(), 1)

    def test_sync_is_idempotent(self):
        user = self._create_user('student3@example.com')
        profile = StudentProfile.objects.create(
            user=user,
            father_name='John Doe',
            father_country='Kenya',
        )
        profile.sync_normalized_fields()
        profile.sync_normalized_fields()
        profile.sync_normalized_fields()
        self.assertEqual(StudentAddress.objects.filter(student=profile).count(), 1)

    def test_supplemental_sync_populates_addresses(self):
        user = self._create_user('student4@example.com')
        application = Application.objects.create(
            student=user,
            status='submitted',
        )
        supplemental = ApplicationSupplementalProfile.objects.create(
            application=application,
            current_country='Tanzania',
            current_region='Dar es Salaam',
            current_district='Kinondoni',
            current_ward='Msasani',
            permanent_country='Tanzania',
            permanent_region='Mwanza',
            professional_qualification_country='Tanzania',
            professional_qualification_location='Arusha',
        )
        supplemental.sync_normalized_fields()
        types = list(
            ApplicationSupplementalAddress.objects
            .filter(supplemental=supplemental)
            .values_list('address_type', flat=True)
        )
        self.assertIn('current', types)
        self.assertIn('permanent', types)
        self.assertIn('professional_qualification', types)

    def test_sync_tolerates_missing_legacy_columns(self):
        """If a legacy column never existed (emergency prod case) sync should
        just skip it, not raise."""
        user = self._create_user('student5@example.com')
        profile = StudentProfile.objects.create(user=user, father_name='John Doe')
        from student_portal.models import _attr
        self.assertEqual(_attr(profile, 'father_definitely_missing_column', 'fallback'), 'fallback')
        profile.sync_normalized_fields()
        self.assertTrue(StudentProfile.objects.filter(pk=profile.pk).exists())

    def test_audit_command_runs(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('audit_student_schema', stdout=out)
        self.assertIn('Applied migrations', out.getvalue())

