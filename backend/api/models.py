from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import date


class User(AbstractUser):
    matricule = models.CharField(max_length=20, null=False, blank=False, unique=True, default='Inconnu')
    fonction = models.CharField(max_length=100, null=False, blank=False, unique=False, default='Inconnu')
    date_naissance = models.DateField(null=False, blank=False, unique=False, default='1900-01-01')
    telephone = models.CharField(max_length=20, null=False, blank=False, unique=True, default='Inconnu')
    email_reciever = models.EmailField(null=True, blank=True, default='Inconnu')
    filiale = models.ForeignKey('Entite', on_delete=models.CASCADE, null=True, blank=True)
    profil = models.ForeignKey('Profil', on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey('CategorieEmploye', on_delete=models.CASCADE, null=True, blank=True)
    direction = models.ForeignKey('Direction', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"


class Entite(models.Model):
    nom = models.CharField(max_length=100, null=False, blank=False, unique=True, default='Inconnu')
    abreviation = models.CharField(max_length=4, null=True, blank=True)

    class Meta:
        verbose_name = "Entite"
        verbose_name_plural = "Entites"

    def __str__(self):
        return f'{self.id} - {self.nom}'


class Direction(models.Model):
    nom = models.CharField(max_length=100, null=False, blank=False)
    filiale = models.ForeignKey('Entite', on_delete=models.CASCADE, null=False, blank=False)
    description = models.CharField(max_length=100, null=True, blank=True, unique=False)

    class Meta:
        verbose_name = "Direction"
        verbose_name_plural = "Directions"
        unique_together = ('nom', 'filiale')
        ordering = ['nom']

    def __str__(self):
        return self.nom


class Profil(models.Model):
    nom = models.CharField(max_length=100, null=False, blank=False, unique=True, default='Inconnu')
    description = models.CharField(max_length=100, null=True, blank=True, unique=False)

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profils"

    def __str__(self):
        return self.nom


class CategorieEmploye(models.Model):
    nom = models.CharField(max_length=100, null=False, blank=False, unique=False, default='Inconnu')
    description = models.CharField(max_length=100, null=True, blank=True, unique=False)

    class Meta:
        verbose_name = "Categorie Employe"
        verbose_name_plural = "Categories Employes"

    def __str__(self):
        return f'{self.id} - {self.nom}'


class Destination(models.Model):
    nom = models.CharField(max_length=100, null=False, blank=False, unique=True, default='Inconnu')
    description = models.CharField(max_length=100, null=True, blank=True, unique=False)

    class Meta:
        verbose_name = "Destination"
        verbose_name_plural = "Destinations"

    def __str__(self):
        return f'{self.id} - {self.nom}'


class Bareme(models.Model):
    filiale = models.ForeignKey('Entite', on_delete=models.CASCADE, null=True, blank=True)
    categorie = models.ForeignKey('CategorieEmploye', on_delete=models.CASCADE, null=True, blank=True)
    destination = models.ForeignKey('Destination', on_delete=models.CASCADE, null=True, blank=True)
    hebergement = models.PositiveIntegerField(default=0)
    perdiem = models.PositiveIntegerField(default=0)
    communication = models.PositiveIntegerField(default=0)
    transport = models.PositiveIntegerField(default=0)
    forfait = models.PositiveIntegerField(default=0)
    longue_duree = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Indemnité de mission"
        verbose_name_plural = "Indemnités de mission"
        unique_together = ('categorie', 'destination')
        ordering = ['categorie', 'destination']

    def __str__(self):
        return f"{self.id} - {self.categorie.nom} - {self.destination.nom}"


class Mission(models.Model):
    STATUTS_MISSION = [
        ('EN_COURS', 'En cours'),
        ('APPROUVEE', 'Approuvée'),
        ('REJETEE', 'Rejetée'),
        ('TERMINEE', 'Terminée'),
    ]

    date_demande = models.DateField()
    entite = models.ForeignKey('Entite', on_delete=models.CASCADE, null=False, blank=False, default=1)
    objet_mission = models.CharField(max_length=255)
    date_depart = models.DateField()
    date_retour = models.DateField()
    lieu_mission = models.CharField(max_length=255)
    statut_mission = models.CharField(
        max_length=20,
        choices=STATUTS_MISSION,
        default='EN_ATTENTE'
    )
    numero_mission = models.CharField(max_length=100, unique=True)
    destination_mission = models.ForeignKey('Destination', on_delete=models.CASCADE, null=False, blank=False, default=1)
    contexte_mission = models.TextField(blank=True, null=True)
    objectifs_mission = models.TextField(blank=True, null=True)
    frais_extra = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    demandeur = models.ForeignKey('User', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'missions'
        verbose_name = 'Mission'
        verbose_name_plural = 'Missions'
        ordering = ['-date_demande']

    def save(self, *args, **kwargs):
        if not self.numero_mission:
            last_mission = Mission.objects.order_by('-id').first()
            num_ordre = (last_mission.id + 1) if last_mission else 1
            annee = self.date_demande.year if self.date_demande else date.today().year
            abrev = self.entite.abreviation
            self.numero_mission = f"{num_ordre}/DRH/{abrev}/{annee}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_mission} - {self.objet_mission}"


class Workflow(models.Model):
    filiale = models.ForeignKey('Entite', on_delete=models.CASCADE)
    numero_etape = models.PositiveIntegerField()
    libelle_etape = models.CharField(max_length=255)

    class Meta:
        db_table = 'workflows'
        verbose_name = 'Workflow'
        verbose_name_plural = 'Workflows'
        ordering = ['filiale', 'numero_etape']
        unique_together = ('filiale', 'numero_etape')

    def __str__(self):
        return f"{self.filiale.abreviation} - Étape {self.numero_etape}: {self.libelle_etape}"


class UserWorkflow(models.Model):
    workflow = models.ForeignKey('Workflow', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workflows')
    class Meta:
        db_table = 'user_workflows'
        verbose_name = 'Utilisateur Workflow'
        verbose_name_plural = 'Utilisateurs Workflow'
        unique_together = ('workflow', 'user')

    def __str__(self):
        return f"{self.user.username} → {self.workflow.libelle_etape}"


class MissionWorkflow(models.Model):
    mission = models.ForeignKey('Mission', on_delete=models.CASCADE, related_name='etapes_workflow')
    workflow = models.ForeignKey('Workflow', on_delete=models.CASCADE, related_name='etapes_mission')
    user_validation = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validations_mission'
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    statut = models.BooleanField(null=True, blank=True)
    commentaire = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'missions_workflow'
        verbose_name = 'Étape de validation de mission'
        verbose_name_plural = 'Étapes de validation des missions'
        ordering = ['mission']
        unique_together = ('mission', 'workflow')

    def __str__(self):
        statut_label = "Validée" if self.statut else "En attente / Rejetée"
        return f"{self.mission.numero_mission}"

