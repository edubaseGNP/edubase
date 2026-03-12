from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_auditlog_level_and_actions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verb', models.CharField(max_length=255, verbose_name='Zpráva')),
                ('target_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Odkaz')),
                ('is_read', models.BooleanField(db_index=True, default=False, verbose_name='Přečteno')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Čas')),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Příjemce',
                )),
            ],
            options={
                'verbose_name': 'Notifikace',
                'verbose_name_plural': 'Notifikace',
                'ordering': ['-created_at'],
            },
        ),
    ]
