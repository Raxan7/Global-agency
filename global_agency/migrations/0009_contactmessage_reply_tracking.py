from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('global_agency', '0008_studentapplication_created_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contactmessage',
            name='replied_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='replied_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contact_message_replies',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='reply_message',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contactmessage',
            name='reply_subject',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
