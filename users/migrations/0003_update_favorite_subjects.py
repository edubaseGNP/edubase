from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0007_subject_definition_and_subjectyear'),
        ('users', '0002_add_favorite_subjects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='favorite_subjects',
            field=models.ManyToManyField(
                blank=True,
                related_name='favorited_by',
                to='materials.subjectyear',
                verbose_name='Oblíbené předměty',
            ),
        ),
    ]
