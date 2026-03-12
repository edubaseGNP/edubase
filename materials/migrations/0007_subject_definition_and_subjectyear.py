import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_global_subjects(apps, schema_editor):
    """Create Subject records from unique names in SubjectYear, then link."""
    SubjectYear = apps.get_model('materials', 'SubjectYear')
    Subject = apps.get_model('materials', 'Subject')

    seen = {}  # slug → Subject instance
    for sy in SubjectYear.objects.order_by('id'):
        slug = sy.slug
        if slug not in seen:
            seen[slug] = Subject.objects.create(
                name=sy.name,
                slug=slug,
                description=sy.description or '',
            )
        sy.subject = seen[slug]
        sy.save(update_fields=['subject'])


def reverse_populate(apps, schema_editor):
    """Reverse: copy subject name/slug/description back to SubjectYear rows."""
    SubjectYear = apps.get_model('materials', 'SubjectYear')
    for sy in SubjectYear.objects.select_related('subject'):
        if sy.subject:
            sy.name = sy.subject.name
            sy.slug = sy.subject.slug
            sy.description = sy.subject.description
            sy.save(update_fields=['name', 'slug', 'description'])


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0006_searchlog_duration_click'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Rename the old Subject table → SubjectYear
        #    This auto-updates all FK/M2M references in the migration state.
        migrations.RenameModel(
            old_name='Subject',
            new_name='SubjectYear',
        ),

        # 2. Create new global Subject model
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Název')),
                ('slug', models.SlugField(max_length=220, unique=True, verbose_name='Slug')),
                ('description', models.TextField(blank=True, verbose_name='Popis')),
            ],
            options={
                'verbose_name': 'Předmět',
                'verbose_name_plural': 'Předměty',
                'ordering': ['name'],
            },
        ),

        # 3. Add nullable subject FK to SubjectYear
        migrations.AddField(
            model_name='subjectyear',
            name='subject',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='years',
                to='materials.subject',
                verbose_name='Předmět',
            ),
        ),

        # 4. Data migration: create Subject records and link SubjectYears
        migrations.RunPython(populate_global_subjects, reverse_populate),

        # 5. Make subject FK non-nullable
        migrations.AlterField(
            model_name='subjectyear',
            name='subject',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='years',
                to='materials.subject',
                verbose_name='Předmět',
            ),
        ),

        # 6. Update unique_together: remove old (school_year, slug), add (subject, school_year)
        migrations.AlterUniqueTogether(
            name='subjectyear',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='subjectyear',
            unique_together={('subject', 'school_year')},
        ),

        # 7. Remove old fields from SubjectYear (now proxied via subject FK)
        migrations.RemoveField(model_name='subjectyear', name='name'),
        migrations.RemoveField(model_name='subjectyear', name='slug'),
        migrations.RemoveField(model_name='subjectyear', name='description'),
    ]
