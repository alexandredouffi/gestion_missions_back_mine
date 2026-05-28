from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0016_missionworkflow_frozen_etape'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sujet', models.CharField(max_length=255)),
                ('destinataires', models.TextField(blank=True)),
                ('statut', models.CharField(choices=[('ENVOYE', 'Envoyé'), ('ECHEC', 'Échec'), ('IGNORE', 'Ignoré — pas de destinataire valide')], max_length=10)),
                ('erreur', models.TextField(blank=True, null=True)),
                ('date_envoi', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Log notification email',
                'verbose_name_plural': 'Logs notifications email',
                'ordering': ['-date_envoi'],
            },
        ),
    ]
