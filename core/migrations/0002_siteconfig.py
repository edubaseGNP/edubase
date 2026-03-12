from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_name', models.CharField(default='EduBase', max_length=200, verbose_name='Název školy')),
                ('school_domain', models.CharField(default='localhost', max_length=100, verbose_name='Doménové jméno')),
                ('google_allowed_domain', models.CharField(
                    blank=True, max_length=100, verbose_name='Povolená Google doména',
                    help_text='Např. skola.cz – ponechte prázdné pro povolení všech domén.',
                )),
                ('setup_complete', models.BooleanField(default=False, verbose_name='Nastavení dokončeno')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Konfigurace webu',
                'verbose_name_plural': 'Konfigurace webu',
            },
        ),
    ]
