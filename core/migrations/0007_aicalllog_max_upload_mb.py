from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_ai_settings'),
        ('materials', '0009_icons_external_url_classroom'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfig',
            name='max_upload_mb',
            field=models.PositiveSmallIntegerField(
                default=50,
                help_text='Maximální velikost nahrávaného souboru v megabajtech.',
                verbose_name='Max. velikost uploadu (MB)',
            ),
        ),
        migrations.CreateModel(
            name='AICallLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('backend', models.CharField(
                    db_index=True, max_length=20,
                    help_text='google | anthropic | ollama | tesseract | pdfminer | office',
                    verbose_name='Backend',
                )),
                ('success', models.BooleanField(db_index=True, default=True, verbose_name='Úspěch')),
                ('chars_extracted', models.PositiveIntegerField(default=0, verbose_name='Znaky')),
                ('duration_ms', models.PositiveIntegerField(default=0, verbose_name='Trvání (ms)')),
                ('error_msg', models.CharField(blank=True, default='', max_length=500, verbose_name='Chyba')),
                ('material', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ai_logs',
                    to='materials.material',
                    verbose_name='Materiál',
                )),
            ],
            options={
                'verbose_name': 'AI/OCR volání',
                'verbose_name_plural': 'AI/OCR volání',
                'ordering': ['-timestamp'],
            },
        ),
    ]
