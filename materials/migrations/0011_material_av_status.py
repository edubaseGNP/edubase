from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0010_alter_subjectyear_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='av_status',
            field=models.CharField(
                choices=[
                    ('pending',  'Čeká na kontrolu'),
                    ('clean',    'Čistý ✓'),
                    ('infected', '⚠ Malware detekován'),
                    ('skipped',  'Přeskočeno'),
                    ('error',    'Chyba kontroly'),
                ],
                default='skipped',   # Existing materials were accepted before ClamAV was added
                db_index=True,
                max_length=10,
                verbose_name='Antivirus',
            ),
        ),
    ]
