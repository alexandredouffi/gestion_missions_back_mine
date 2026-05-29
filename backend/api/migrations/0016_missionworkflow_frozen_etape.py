from django.db import migrations, models


def nettoyer_orphelins(apps, schema_editor):
    Delegation = apps.get_model('api', 'Delegation')
    Mission = apps.get_model('api', 'Mission')
    ids_missions_valides = set(Mission.objects.values_list('pk', flat=True))
    Delegation.objects.exclude(mission_id__in=ids_missions_valides).delete()


def backfill_etape_fields(apps, schema_editor):
    MissionWorkflow = apps.get_model('api', 'MissionWorkflow')
    for mw in MissionWorkflow.objects.select_related('workflow').all():
        mw.numero_etape = mw.workflow.numero_etape
        mw.libelle_etape = mw.workflow.libelle_etape
        mw.save(update_fields=['numero_etape', 'libelle_etape'])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_validation_comptable_justification'),
    ]

    operations = [
        migrations.RunPython(nettoyer_orphelins, migrations.RunPython.noop),
        migrations.AddField(
            model_name='missionworkflow',
            name='numero_etape',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='missionworkflow',
            name='libelle_etape',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(backfill_etape_fields, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='missionworkflow',
            options={
                'ordering': ['mission', 'numero_etape'],
                'verbose_name': 'Étape de validation de mission',
                'verbose_name_plural': 'Étapes de validation des missions',
            },
        ),
    ]
