from django.db import migrations, models
import globalagency_project.storage


class Migration(migrations.Migration):

    dependencies = [
        ('student_portal', '0015_alter_document_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='file',
            field=models.FileField(
                storage=globalagency_project.storage.PdfFriendlyCloudinaryStorage(),
                upload_to='documents/',
            ),
        ),
    ]
