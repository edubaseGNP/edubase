from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0007_subject_definition_and_subjectyear'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subjectyear',
            name='created_at',
        ),
    ]
