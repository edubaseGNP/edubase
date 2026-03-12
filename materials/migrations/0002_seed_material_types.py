from django.db import migrations

DEFAULT_MATERIAL_TYPES = [
    ('Podklady', 'podklady', 1),
    ('Testy', 'testy', 2),
    ('Kontrolní otázky', 'kontrolni-otazky', 3),
    ('Domácí úkoly', 'domaci-ukoly', 4),
    ('Ostatní', 'ostatni', 99),
]


def seed_material_types(apps, schema_editor):
    MaterialType = apps.get_model('materials', 'MaterialType')
    for name, slug, order in DEFAULT_MATERIAL_TYPES:
        MaterialType.objects.get_or_create(slug=slug, defaults={'name': name, 'order': order})


def unseed_material_types(apps, schema_editor):
    MaterialType = apps.get_model('materials', 'MaterialType')
    slugs = [slug for _, slug, _ in DEFAULT_MATERIAL_TYPES]
    MaterialType.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_material_types, reverse_code=unseed_material_types),
    ]
