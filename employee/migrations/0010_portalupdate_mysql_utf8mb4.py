from django.db import migrations


def convert_portalupdate_table_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE employee_portalupdate "
            "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0009_userprofile_partner_approval_fields'),
    ]

    operations = [
        migrations.RunPython(
            convert_portalupdate_table_to_utf8mb4,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
