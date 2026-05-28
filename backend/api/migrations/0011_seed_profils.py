from django.db import migrations

PROFILS = [
    {"nom": "Utilisateur classique", "description": "Accès standard à la gestion des missions"},
    {"nom": "Comptable", "description": "Accès aux justificatifs de toutes les missions"},
    {"nom": "Signataire", "description": "Approbation et rejet des étapes de workflow"},
    {"nom": "Trésorier", "description": "Enregistrement des paiements de missions"},
    {"nom": "Administrateur", "description": "Gestion des référentiels (entités, barèmes, workflows)"},
]


def seed_profils(apps, schema_editor):
    Profil = apps.get_model("api", "Profil")
    for data in PROFILS:
        Profil.objects.get_or_create(nom=data["nom"], defaults={"description": data["description"]})


def unseed_profils(apps, schema_editor):
    Profil = apps.get_model("api", "Profil")
    Profil.objects.filter(nom__in=[p["nom"] for p in PROFILS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_justificationhebergement_piecejustificative"),
    ]

    operations = [
        migrations.RunPython(seed_profils, unseed_profils),
    ]
