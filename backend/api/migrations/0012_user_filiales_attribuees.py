from django.db import migrations, models


def fix_orphan_profils(apps, schema_editor):
    User = apps.get_model("api", "User")
    Profil = apps.get_model("api", "Profil")
    valid_ids = set(Profil.objects.values_list("id", flat=True))
    User.objects.exclude(profil_id__isnull=True).exclude(profil_id__in=valid_ids).update(profil=None)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0011_seed_profils"),
    ]

    operations = [
        migrations.RunPython(fix_orphan_profils, migrations.RunPython.noop),
        migrations.AddField(
            model_name="user",
            name="filiales_attribuees",
            field=models.ManyToManyField(
                blank=True,
                related_name="utilisateurs_attribues",
                to="api.entite",
            ),
        ),
    ]
