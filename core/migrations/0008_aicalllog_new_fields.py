from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_aicalllog_max_upload_mb'),
    ]

    operations = [
        migrations.AddField(
            model_name='aicalllog',
            name='file_type',
            field=models.CharField(
                choices=[
                    ('image', 'Obrázek'),
                    ('pdf_text', 'PDF (textová vrstva)'),
                    ('pdf_ocr', 'PDF (OCR)'),
                    ('office', 'Office dokument'),
                    ('unknown', 'Neznámý'),
                ],
                db_index=True,
                default='unknown',
                max_length=10,
                verbose_name='Typ souboru',
            ),
        ),
        migrations.AddField(
            model_name='aicalllog',
            name='model_name',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Model'),
        ),
        migrations.AddField(
            model_name='aicalllog',
            name='attempt',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='Pokus č.'),
        ),
        migrations.AddField(
            model_name='aicalllog',
            name='tokens_used',
            field=models.PositiveIntegerField(default=0, verbose_name='Tokeny'),
        ),
        migrations.AddField(
            model_name='aicalllog',
            name='trigger',
            field=models.CharField(
                choices=[
                    ('upload', 'Nahrání'),
                    ('reprocess', 'Přepracování'),
                ],
                db_index=True,
                default='upload',
                max_length=15,
                verbose_name='Spuštění',
            ),
        ),
    ]
