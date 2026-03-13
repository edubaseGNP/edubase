"""
Add icon + external_url to Material, classroom_link to SubjectYear,
and make Material.file optional (blank=True).
"""
from django.db import migrations, models
import materials.models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0008_remove_subjectyear_created_at'),
    ]

    operations = [
        # Material: icon field
        migrations.AddField(
            model_name='material',
            name='icon',
            field=models.CharField(default='📄', max_length=20, verbose_name='Ikona'),
        ),
        # Material: external_url field
        migrations.AddField(
            model_name='material',
            name='external_url',
            field=models.URLField(blank=True, default='', max_length=1000, verbose_name='Externí odkaz'),
        ),
        # Material.file becomes optional
        migrations.AlterField(
            model_name='material',
            name='file',
            field=models.FileField(
                blank=True,
                upload_to=materials.models.material_upload_path,
                verbose_name='Soubor',
            ),
        ),
        # SubjectYear: classroom_link field
        migrations.AddField(
            model_name='subjectyear',
            name='classroom_link',
            field=models.URLField(blank=True, default='', max_length=500, verbose_name='Google Classroom odkaz'),
        ),
    ]
