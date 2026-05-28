from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def fix_orphan_delegations(apps, schema_editor):
    Delegation = apps.get_model("api", "Delegation")
    Mission = apps.get_model("api", "Mission")
    valid_ids = set(Mission.objects.values_list("id", flat=True))
    Delegation.objects.exclude(mission_id__in=valid_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0012_user_filiales_attribuees"),
    ]

    operations = [
        migrations.RunPython(fix_orphan_delegations, migrations.RunPython.noop),
        migrations.AddField(
            model_name="paiement",
            name="enregistre_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="paiements_enregistres",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
