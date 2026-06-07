from django.db import migrations


def rename_supporter_to_stadium(apps, schema_editor):
    ShirtVersion = apps.get_model('kits', 'ShirtVersion')
    ShirtVersion.objects.filter(code='SUPPORTER').update(name='Stadium')


def rename_stadium_to_supporter(apps, schema_editor):
    ShirtVersion = apps.get_model('kits', 'ShirtVersion')
    ShirtVersion.objects.filter(code='SUPPORTER').update(name='Supporter Version')


class Migration(migrations.Migration):
    dependencies = [
        ('kits', '0029_shirtversion_kittype_kit_kit_type_ref_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_supporter_to_stadium, rename_stadium_to_supporter),
    ]
