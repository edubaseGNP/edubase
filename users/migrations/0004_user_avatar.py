from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_update_favorite_subjects'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/', verbose_name='Profilový obrázek'),
        ),
    ]
