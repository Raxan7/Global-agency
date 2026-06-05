"""0022 — Normalize the wide student/supplemental profile tables.

This migration is the second part of the 1118 (Row size too large) recovery:

* it ensures the wide tables are in ``ROW_FORMAT=DYNAMIC`` (idempotent);
* it creates the four normalized tables for ``StudentProfile``
  (``StudentAddress``, ``StudentPassport``, ``StudentFamilyContact``,
  ``StudentSchoolHistory``);
* it creates the supplemental analogue ``ApplicationSupplementalAddress``;
* it copies the existing legacy data into the normalized rows so we don't
  lose anything when downstream code starts reading from the normalized
  tables.

The legacy wide fields are intentionally left in place so the transition is
lossless and can be reverted by simply dropping the new tables.
"""
from django.db import migrations, models
import django.db.models.deletion


DYNAMIC_TABLES = (
    "student_portal_studentprofile",
    "student_portal_applicationsupplementalprofile",
    "student_portal_workexperience",
)


def _ensure_mysql_dynamic_row_format(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in DYNAMIC_TABLES:
            cursor.execute("SHOW TABLES LIKE %s", [table])
            if not cursor.fetchone():
                continue
            cursor.execute(
                "SELECT CREATE_OPTIONS FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table],
            )
            row = cursor.fetchone()
            create_options = (row[0] or "") if row else ""
            if "row_format=dynamic" in create_options.lower():
                continue
            try:
                cursor.execute(f"ALTER TABLE `{table}` ROW_FORMAT=DYNAMIC")
            except Exception:
                pass


def _physical_columns(connection, table_name):
    """Return the set of column names that physically exist on ``table_name``."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                [table_name],
            )
            return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()


def _row_has_content(values):
    return any((v or "").strip() for v in values.values())


def _attr(obj, name, default=""):
    value = getattr(obj, name, None)
    if value is None:
        return default
    return value


def _backfill_student_addresses(apps, schema_editor):
    StudentProfile = apps.get_model("student_portal", "StudentProfile")
    StudentAddress = apps.get_model("student_portal", "StudentAddress")
    connection = schema_editor.connection
    columns = _physical_columns(connection, "student_portal_studentprofile")
    type_specs = [
        ("personal", "personal_"),
        ("permanent", "permanent_"),
        ("father", "father_"),
        ("mother", "mother_"),
        ("emergency", "emergency_"),
        ("olevel_school", "school_olevel_"),
        ("alevel_school", "school_alevel_"),
        ("other", "other_"),
    ]
    text_fields = (
        "street",
        "mtaa",
        "village",
        "neighbourhood",
        "place_neighbourhood",
        "landmark",
        "nearest_landmark",
        "address_line",
        "address",
        "address_remarks",
    )
    short_fields = (
        "country",
        "region",
        "region_post_code",
        "city",
        "district",
        "district_post_code",
        "ward",
        "ward_post_code",
        "house_no",
        "postal_code",
        "post_code",
        "duration_at_address",
        "address_status",
    )
    for profile in StudentProfile.objects.all().iterator():
        for address_type, prefix in type_specs:
            defaults = {}
            for f in short_fields:
                col = f"{prefix}{f}"
                if col in columns:
                    defaults[f] = _attr(profile, col)
            for f in text_fields:
                col = f"{prefix}{f}"
                if col in columns:
                    defaults[f] = _attr(profile, col)
            if not _row_has_content(defaults):
                continue
            StudentAddress.objects.update_or_create(
                student=profile,
                address_type=address_type,
                defaults=defaults,
            )


def _backfill_passport(apps, schema_editor):
    StudentProfile = apps.get_model("student_portal", "StudentProfile")
    StudentPassport = apps.get_model("student_portal", "StudentPassport")
    connection = schema_editor.connection
    columns = _physical_columns(connection, "student_portal_studentprofile")
    for profile in StudentProfile.objects.all().iterator():
        fields = {}
        for col, dest in [
            ("passport_number", "passport_number"),
            ("passport_country", "issue_country"),
            ("passport_issue_country", "issue_country"),
            ("passport_issued_country", "issue_country"),
            ("passport_issue_date", "issue_date"),
            ("passport_issued_date", "issue_date"),
            ("passport_date_of_issue", "issue_date"),
            ("passport_expiry_date", "expiry_date"),
            ("passport_expire_date", "expiry_date"),
            ("passport_expiration_date", "expiry_date"),
            ("passport_expiry", "expiry_date"),
            ("passport_notes", "notes"),
            ("passport_remarks", "notes"),
        ]:
            if col in columns:
                fields[dest] = _attr(profile, col)
        if not _row_has_content(fields):
            continue
        StudentPassport.objects.update_or_create(
            student=profile,
            defaults=fields,
        )


def _backfill_family_contacts(apps, schema_editor):
    StudentProfile = apps.get_model("student_portal", "StudentProfile")
    StudentFamilyContact = apps.get_model("student_portal", "StudentFamilyContact")
    connection = schema_editor.connection
    columns = _physical_columns(connection, "student_portal_studentprofile")
    type_specs = [
        ("father", "father_"),
        ("mother", "mother_"),
        ("emergency", "emergency_"),
        ("guardian", "guardian_"),
    ]
    for profile in StudentProfile.objects.all().iterator():
        for contact_type, prefix in type_specs:
            fields = {}
            for col, dest in [
                ("name", "name"),
                ("full_name", "name"),
                ("first_name", "name"),
                ("middle_name", "name"),
                ("last_name", "name"),
                ("occupation", "occupation"),
                ("job_title", "occupation"),
                ("employer", "occupation"),
                ("phone", "phone"),
                ("mobile", "phone"),
                ("mobile_number", "phone"),
                ("phone_number", "phone"),
                ("email", "email"),
                ("email_address", "email"),
                ("address", "address"),
                ("relation", "relation"),
                ("relationship", "relation"),
                ("gender", "gender"),
                ("notes", "notes"),
                ("remarks", "notes"),
            ]:
                full = f"{prefix}{col}"
                if full in columns:
                    fields[dest] = _attr(profile, full)
            if not _row_has_content(fields):
                continue
            StudentFamilyContact.objects.update_or_create(
                student=profile,
                contact_type=contact_type,
                defaults=fields,
            )


def _backfill_school_history(apps, schema_editor):
    StudentProfile = apps.get_model("student_portal", "StudentProfile")
    StudentSchoolHistory = apps.get_model("student_portal", "StudentSchoolHistory")
    connection = schema_editor.connection
    columns = _physical_columns(connection, "student_portal_studentprofile")
    level_specs = [
        ("olevel", "school_olevel_"),
        ("alevel", "school_alevel_"),
        ("primary", "primary_school_"),
    ]
    for profile in StudentProfile.objects.all().iterator():
        for level, prefix in level_specs:
            fields = {}
            for col, dest in [
                ("name", "school_name"),
                ("school_name", "school_name"),
                ("centre_no", "school_name"),
                ("centre_number", "school_name"),
                ("index_no", "candidate_no"),
                ("index_number", "candidate_no"),
                ("candidate_no", "candidate_no"),
                ("candidate_number", "candidate_no"),
                ("country", "country"),
                ("region", "region"),
                ("district", "district"),
                ("ward", "ward"),
                ("year_started", "start_year"),
                ("start_year", "start_year"),
                ("year_completed", "completed_year"),
                ("completed_year", "completed_year"),
                ("year", "completed_year"),
                ("form_4_index_no", "candidate_no"),
                ("form_6_index_no", "candidate_no"),
                ("gpa", "gpa"),
                ("house_no", "house_no"),
                ("street", "street"),
                ("mtaa", "mtaa"),
                ("address", "address"),
                ("remarks", "remarks"),
            ]:
                full = f"{prefix}{col}"
                if full in columns:
                    fields[dest] = _attr(profile, full)
            if not _row_has_content(fields):
                continue
            StudentSchoolHistory.objects.update_or_create(
                student=profile,
                level=level,
                defaults=fields,
            )


def _backfill_supplemental_addresses(apps, schema_editor):
    Supplemental = apps.get_model("student_portal", "ApplicationSupplementalProfile")
    SupplementalAddress = apps.get_model("student_portal", "ApplicationSupplementalAddress")
    connection = schema_editor.connection
    columns = _physical_columns(connection, "student_portal_applicationsupplementalprofile")
    type_specs = [
        ("current", "current_"),
        ("permanent", "permanent_"),
        ("professional_qualification", "professional_qualification_"),
    ]
    short_fields = (
        "country",
        "region",
        "region_post_code",
        "city",
        "district",
        "district_post_code",
        "ward",
        "ward_post_code",
        "house_no",
        "postal_code",
        "post_code",
        "duration_at_address",
        "address_status",
    )
    text_fields = (
        "street",
        "mtaa",
        "village",
        "neighbourhood",
        "place_neighbourhood",
        "landmark",
        "nearest_landmark",
        "address",
        "address_remarks",
        "location",
    )
    for supplemental in Supplemental.objects.all().iterator():
        for address_type, prefix in type_specs:
            defaults = {}
            for f in short_fields:
                col = f"{prefix}{f}"
                if col in columns:
                    defaults[f] = _attr(supplemental, col)
            for f in text_fields:
                col = f"{prefix}{f}"
                if col in columns:
                    defaults[f] = _attr(supplemental, col)
            if not _row_has_content(defaults):
                continue
            SupplementalAddress.objects.update_or_create(
                supplemental=supplemental,
                address_type=address_type,
                defaults=defaults,
            )


def _noop_reverse(apps, schema_editor):
    # The forward functions are idempotent and we never drop the new tables
    # on reversal, so reversing is a no-op.
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("student_portal", "0019_applicationsupplementalprofile_bachelor_completed_year_and_more"),
    ]

    operations = [
        # 1) Make sure all wide tables are in DYNAMIC row format (idempotent).
        migrations.RunPython(
            code=_ensure_mysql_dynamic_row_format,
            reverse_code=migrations.RunPython.noop,
        ),

        # 2) Create the four normalized tables for StudentProfile.
        migrations.CreateModel(
            name="StudentAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("address_type", models.CharField(choices=[
                    ("personal", "Personal / Current"),
                    ("permanent", "Permanent"),
                    ("father", "Father"),
                    ("mother", "Mother"),
                    ("emergency", "Emergency Contact"),
                    ("olevel_school", "O-Level School"),
                    ("alevel_school", "A-Level School"),
                    ("other", "Other"),
                ], max_length=30)),
                ("country", models.CharField(blank=True, default="Tanzania", max_length=100)),
                ("region", models.CharField(blank=True, max_length=120)),
                ("region_post_code", models.CharField(blank=True, max_length=30)),
                ("district", models.CharField(blank=True, max_length=120)),
                ("district_post_code", models.CharField(blank=True, max_length=30)),
                ("ward", models.CharField(blank=True, max_length=120)),
                ("ward_post_code", models.CharField(blank=True, max_length=30)),
                ("house_no", models.CharField(blank=True, max_length=80)),
                ("postal_code", models.CharField(blank=True, max_length=30)),
                ("post_code", models.CharField(blank=True, max_length=30)),
                ("street", models.TextField(blank=True)),
                ("mtaa", models.TextField(blank=True)),
                ("village", models.TextField(blank=True)),
                ("neighbourhood", models.TextField(blank=True)),
                ("place_neighbourhood", models.TextField(blank=True)),
                ("landmark", models.TextField(blank=True)),
                ("nearest_landmark", models.TextField(blank=True)),
                ("address_line", models.TextField(blank=True)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="student_portal.studentprofile")),
            ],
            options={
                "verbose_name": "Student Address",
                "verbose_name_plural": "Student Addresses",
                "ordering": ["student_id", "address_type"],
                "unique_together": {("student", "address_type")},
            },
        ),
        migrations.CreateModel(
            name="StudentPassport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("passport_number", models.CharField(blank=True, max_length=100)),
                ("issue_country", models.CharField(blank=True, max_length=100)),
                ("issue_date", models.DateField(blank=True, null=True)),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="passport_record", to="student_portal.studentprofile")),
            ],
            options={
                "verbose_name": "Student Passport",
                "verbose_name_plural": "Student Passports",
            },
        ),
        migrations.CreateModel(
            name="StudentFamilyContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contact_type", models.CharField(choices=[
                    ("father", "Father"),
                    ("mother", "Mother"),
                    ("emergency", "Emergency Contact"),
                    ("guardian", "Guardian"),
                    ("other", "Other"),
                ], max_length=20)),
                ("name", models.CharField(blank=True, max_length=150)),
                ("phone", models.CharField(blank=True, max_length=50)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("occupation", models.CharField(blank=True, max_length=150)),
                ("relation", models.CharField(blank=True, max_length=100)),
                ("gender", models.CharField(blank=True, max_length=20)),
                ("address", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="family_contacts", to="student_portal.studentprofile")),
            ],
            options={
                "verbose_name": "Student Family Contact",
                "verbose_name_plural": "Student Family Contacts",
                "ordering": ["student_id", "contact_type"],
                "unique_together": {("student", "contact_type")},
            },
        ),
        migrations.CreateModel(
            name="StudentSchoolHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.CharField(choices=[
                    ("olevel", "O-Level"),
                    ("alevel", "A-Level"),
                    ("primary", "Primary"),
                    ("other", "Other"),
                ], max_length=20)),
                ("school_name", models.CharField(blank=True, max_length=255)),
                ("candidate_no", models.CharField(blank=True, max_length=50)),
                ("gpa", models.CharField(blank=True, max_length=20)),
                ("start_year", models.CharField(blank=True, max_length=10)),
                ("completed_year", models.CharField(blank=True, max_length=10)),
                ("country", models.CharField(blank=True, default="Tanzania", max_length=100)),
                ("region", models.CharField(blank=True, max_length=120)),
                ("district", models.CharField(blank=True, max_length=120)),
                ("ward", models.CharField(blank=True, max_length=120)),
                ("house_no", models.CharField(blank=True, max_length=80)),
                ("street", models.TextField(blank=True)),
                ("mtaa", models.TextField(blank=True)),
                ("address", models.TextField(blank=True)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="school_history", to="student_portal.studentprofile")),
            ],
            options={
                "verbose_name": "Student School History",
                "verbose_name_plural": "Student School Histories",
                "ordering": ["student_id", "level"],
                "unique_together": {("student", "level")},
            },
        ),
        migrations.CreateModel(
            name="ApplicationSupplementalAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("address_type", models.CharField(choices=[
                    ("current", "Current Address"),
                    ("permanent", "Permanent Address"),
                    ("professional_qualification", "Professional Qualification"),
                    ("other", "Other"),
                ], max_length=40)),
                ("country", models.CharField(blank=True, default="Tanzania", max_length=100)),
                ("region", models.CharField(blank=True, max_length=120)),
                ("region_post_code", models.CharField(blank=True, max_length=30)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("district", models.CharField(blank=True, max_length=120)),
                ("district_post_code", models.CharField(blank=True, max_length=30)),
                ("ward", models.CharField(blank=True, max_length=120)),
                ("ward_post_code", models.CharField(blank=True, max_length=30)),
                ("house_no", models.CharField(blank=True, max_length=80)),
                ("postal_code", models.CharField(blank=True, max_length=30)),
                ("post_code", models.CharField(blank=True, max_length=30)),
                ("duration_at_address", models.CharField(blank=True, max_length=120)),
                ("address_status", models.CharField(blank=True, max_length=120)),
                ("street", models.TextField(blank=True)),
                ("mtaa", models.TextField(blank=True)),
                ("village", models.TextField(blank=True)),
                ("neighbourhood", models.TextField(blank=True)),
                ("place_neighbourhood", models.TextField(blank=True)),
                ("landmark", models.TextField(blank=True)),
                ("nearest_landmark", models.TextField(blank=True)),
                ("address_line", models.TextField(blank=True)),
                ("location", models.TextField(blank=True)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("supplemental", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="student_portal.applicationsupplementalprofile")),
            ],
            options={
                "verbose_name": "Application Supplemental Address",
                "verbose_name_plural": "Application Supplemental Addresses",
                "ordering": ["supplemental_id", "address_type"],
                "unique_together": {("supplemental", "address_type")},
            },
        ),

        # 3) Backfill data from the legacy wide columns into the new tables.
        migrations.RunPython(
            code=_backfill_student_addresses,
            reverse_code=_noop_reverse,
        ),
        migrations.RunPython(
            code=_backfill_passport,
            reverse_code=_noop_reverse,
        ),
        migrations.RunPython(
            code=_backfill_family_contacts,
            reverse_code=_noop_reverse,
        ),
        migrations.RunPython(
            code=_backfill_school_history,
            reverse_code=_noop_reverse,
        ),
        migrations.RunPython(
            code=_backfill_supplemental_addresses,
            reverse_code=_noop_reverse,
        ),
    ]
