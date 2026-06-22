from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('global_agency', '0009_contactmessage_reply_tracking'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='studentapplication',
            name='address',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='alevel_country',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='alevel_region',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='emergency_gender',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='olevel_country',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='olevel_region',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='preferred_country_4',
        ),
        migrations.RemoveField(
            model_name='studentapplication',
            name='preferred_program_4',
        ),
    ]
