from django.db import migrations, models
import cloudinary_storage.storage


class Migration(migrations.Migration):

    dependencies = [
        ('student_portal', '0014_alter_document_document_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='file',
            field=models.FileField(
                storage=cloudinary_storage.storage.RawMediaCloudinaryStorage(),
                upload_to='documents/',
            ),
        ),
    ]
