from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0005_searchlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='searchlog',
            name='duration_ms',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Doba (ms)'),
        ),
        migrations.AddField(
            model_name='searchlog',
            name='clicked_result_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Klik na výsledek'),
        ),
    ]
