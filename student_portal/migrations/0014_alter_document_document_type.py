from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student_portal', '0013_applicationsupplementalprofile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='document_type',
            field=models.CharField(
                choices=[
                    ('passport', 'Passport Copy'),
                    ('passport_photo', 'Passport Photo'),
                    ('ordinary_level', 'Ordinary Level Certificate'),
                    ('advanced_level', 'Advanced Level Certificate'),
                    ('academic_transcript', 'Academic Transcript'),
                    ('degree_certificate', 'Degree / Diploma Certificate'),
                    ('application_form', 'Application Form'),
                    ('recommendation_letter', 'Recommendation Letter'),
                    ('sop', 'Statement of Purpose / Motivation Letter'),
                    ('cv', 'CV / Resume'),
                    ('language_test', 'English Proficiency Test (IELTS / TOEFL)'),
                    ('proof_of_funds', 'Proof of Funds'),
                    ('health_insurance', 'Health Insurance'),
                    ('financial_documents', 'Financial Documents (Legacy)'),
                ],
                max_length=50,
            ),
        ),
    ]
