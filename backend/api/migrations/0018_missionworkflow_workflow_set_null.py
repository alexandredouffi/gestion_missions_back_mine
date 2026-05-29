from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_notificationlog'),
    ]

    operations = [
        # Rendre le FK nullable + SET_NULL au lieu de CASCADE
        migrations.AlterField(
            model_name='missionworkflow',
            name='workflow',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='etapes_mission',
                to='api.workflow',
            ),
        ),
        # Supprimer l'unique_together qui impliquait le FK workflow
        migrations.AlterUniqueTogether(
            name='missionworkflow',
            unique_together=set(),
        ),
    ]
