from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import date, timedelta
import uuid
import random


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
    filiales_attribuees = models.ManyToManyField('Entite', blank=True, related_name='utilisateurs_attribues')

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
        unique_together = ('filiale', 'categorie', 'destination')
        ordering = ['categorie', 'destination']

    def __str__(self):
        return f"{self.id} - {self.categorie.nom} - {self.destination.nom}"


class Mission(models.Model):
    STATUTS_MISSION = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours'),
        ('APPROUVEE', 'Approuvée'),
        ('REJETEE', 'Rejetée'),
        ('TERMINEE', 'Terminée'),
    ]

    date_demande = models.DateField()
    entite = models.ForeignKey('Entite', on_delete=models.CASCADE)
    objet_mission = models.CharField(max_length=255)
    date_depart = models.DateField()
    date_retour = models.DateField()
    lieu_mission = models.CharField(max_length=255)
    statut_mission = models.CharField(max_length=20, choices=STATUTS_MISSION, default='EN_ATTENTE')
    numero_mission = models.CharField(max_length=100, unique=True, blank=True)
    destination_mission = models.ForeignKey('Destination', on_delete=models.CASCADE)
    contexte_mission = models.TextField(blank=True, null=True)
    objectifs_mission = models.TextField(blank=True, null=True)
    frais_extra = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    demandeur = models.ForeignKey('User', on_delete=models.CASCADE)

    class Meta:
        db_table = 'missions'
        verbose_name = 'Mission'
        verbose_name_plural = 'Missions'
        ordering = ['-date_demande']

    def save(self, *args, **kwargs):
        if not self.pk:
            self.numero_mission = str(uuid.uuid4())
            super().save(*args, **kwargs)
            annee = self.date_demande.year if self.date_demande else date.today().year
            self.numero_mission = f"{self.id}/DRH/{self.entite.abreviation}/{annee}"
            super().save(update_fields=['numero_mission'])
            self._creer_etapes_workflow()
        else:
            super().save(*args, **kwargs)

    def _creer_etapes_workflow(self):
        etapes = Workflow.objects.filter(filiale=self.entite).order_by('numero_etape')
        MissionWorkflow.objects.bulk_create([
            MissionWorkflow(
                mission=self,
                workflow=etape,
                numero_etape=etape.numero_etape,
                libelle_etape=etape.libelle_etape,
                user_validation=etape.user,
            )
            for etape in etapes
        ])

    def __str__(self):
        return f"{self.numero_mission} - {self.objet_mission}"


class Workflow(models.Model):
    filiale = models.ForeignKey('Entite', on_delete=models.CASCADE)
    numero_etape = models.PositiveIntegerField()
    libelle_etape = models.CharField(max_length=255)
    user = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='etapes_workflow')

    class Meta:
        db_table = 'workflows'
        verbose_name = 'Workflow'
        verbose_name_plural = 'Workflows'
        ordering = ['filiale', 'numero_etape']
        unique_together = ('filiale', 'numero_etape')

    def __str__(self):
        return f"{self.filiale.abreviation} - Étape {self.numero_etape}: {self.libelle_etape}"


class Delegation(models.Model):
    mission = models.ForeignKey('Mission', on_delete=models.CASCADE, related_name='delegations')
    employe = models.ForeignKey('User', on_delete=models.CASCADE, related_name='delegations')
    est_chef = models.BooleanField(default=False)
    bareme = models.ForeignKey('Bareme', on_delete=models.SET_NULL, null=True, blank=True)
    duree = models.PositiveIntegerField(default=0)
    est_longue_duree = models.BooleanField(default=False)
    montant_hebergement = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_perdiem = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_communication = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_transport = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Membre de délégation"
        verbose_name_plural = "Membres de délégation"
        unique_together = ('mission', 'employe')

    def save(self, *args, **kwargs):
        if self.est_chef:
            Delegation.objects.filter(mission=self.mission, est_chef=True).exclude(pk=self.pk).update(est_chef=False)

        if not self.bareme_id and self.employe.filiale and self.employe.category:
            try:
                self.bareme = Bareme.objects.get(
                    filiale=self.employe.filiale,
                    categorie=self.employe.category,
                    destination=self.mission.destination_mission
                )
            except Bareme.DoesNotExist:
                pass

        self._calculer_montants()
        super().save(*args, **kwargs)

    def _calculer_montants(self):
        duree = (self.mission.date_retour - self.mission.date_depart).days + 1
        self.duree = duree
        self.est_longue_duree = duree > 15

        if not self.bareme:
            return

        if self.est_longue_duree:
            self.montant_hebergement = 0
            self.montant_perdiem = 0
            self.montant_communication = 0
            self.montant_transport = 0
            self.montant_total = self.bareme.forfait * duree
        else:
            self.montant_hebergement = self.bareme.hebergement * (duree - 1)
            self.montant_perdiem = self.bareme.perdiem * duree
            self.montant_communication = self.bareme.communication
            self.montant_transport = self.bareme.transport
            self.montant_total = (
                self.montant_hebergement + self.montant_perdiem +
                self.montant_communication + self.montant_transport
            )

    def __str__(self):
        chef = " (Chef)" if self.est_chef else ""
        return f"{self.employe.username}{chef} → {self.mission.numero_mission}"


class Paiement(models.Model):
    MODE_CHOICES = [
        ('CHEQUE', 'Chèque'),
        ('LIQUIDE', 'Liquide'),
    ]

    delegation = models.OneToOneField('Delegation', on_delete=models.CASCADE, related_name='paiement')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    reference_cheque = models.CharField(max_length=100, null=True, blank=True)
    cheque_document = models.FileField(upload_to='cheques/%Y/%m/', null=True, blank=True)
    date_paiement = models.DateField()
    effectue = models.BooleanField(default=False)
    enregistre_par = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements_enregistres')

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def save(self, *args, **kwargs):
        if self.delegation.mission.statut_mission != 'APPROUVEE':
            raise ValueError("Le paiement ne peut être enregistré que pour une mission approuvée.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.delegation.employe.username} — {self.mode} — {self.montant}"


class JustificationHebergement(models.Model):
    delegation = models.OneToOneField('Delegation', on_delete=models.CASCADE, related_name='justification_hebergement')
    date_soumission = models.DateTimeField(auto_now_add=True)
    valide_par_comptable = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='justifications_validees'
    )
    date_validation_comptable = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Justification hébergement"
        verbose_name_plural = "Justifications hébergement"

    @property
    def montant_total_justifie(self):
        return self.pieces.aggregate(
            total=models.Sum('montant')
        )['total'] or 0

    @property
    def est_complet(self):
        return self.montant_total_justifie >= self.delegation.montant_hebergement

    def __str__(self):
        return f"Justification — {self.delegation.employe.username} — {self.delegation.mission.numero_mission}"


class PieceJustificative(models.Model):
    justification = models.ForeignKey('JustificationHebergement', on_delete=models.CASCADE, related_name='pieces')
    libelle = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    document = models.FileField(upload_to='justifications/%Y/%m/')
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce justificative"
        verbose_name_plural = "Pièces justificatives"
        ordering = ['date_ajout']

    def __str__(self):
        return f"{self.libelle} — {self.montant} F"


class OTPCode(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Code OTP"
        verbose_name_plural = "Codes OTP"
        ordering = ['-created_at']

    @classmethod
    def generer(cls, user):
        cls.objects.filter(user=user, is_used=False).delete()
        code = f"{random.randint(0, 999999):06d}"
        return cls.objects.create(
            user=user,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

    @property
    def est_valide(self):
        return not self.is_used and timezone.now() <= self.expires_at

    def __str__(self):
        return f"OTP {self.user.username} — {'valide' if self.est_valide else 'expiré'}"


class NotificationLog(models.Model):
    STATUTS = [
        ('ENVOYE', 'Envoyé'),
        ('ECHEC', 'Échec'),
        ('IGNORE', 'Ignoré — pas de destinataire valide'),
    ]

    sujet = models.CharField(max_length=255)
    destinataires = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=STATUTS)
    erreur = models.TextField(blank=True, null=True)
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log notification email"
        verbose_name_plural = "Logs notifications email"
        ordering = ['-date_envoi']

    def __str__(self):
        return f"[{self.statut}] {self.sujet} — {self.date_envoi:%d/%m/%Y %H:%M}"


class MissionWorkflow(models.Model):
    STATUTS = [
        ('EN_ATTENTE', 'En attente'),
        ('APPROUVE', 'Approuvé'),
        ('REJETE', 'Rejeté'),
    ]

    mission = models.ForeignKey('Mission', on_delete=models.CASCADE, related_name='etapes_workflow')
    workflow = models.ForeignKey('Workflow', on_delete=models.SET_NULL, null=True, blank=True, related_name='etapes_mission')
    numero_etape = models.PositiveIntegerField(default=0)
    libelle_etape = models.CharField(max_length=255, blank=True, default='')
    user_validation = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validations_mission'
    )
    statut = models.CharField(max_length=20, choices=STATUTS, default='EN_ATTENTE')
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'missions_workflow'
        verbose_name = 'Étape de validation de mission'
        verbose_name_plural = 'Étapes de validation des missions'
        ordering = ['mission', 'numero_etape']
    def __str__(self):
        return f"{self.mission.numero_mission} - Étape {self.numero_etape} ({self.libelle_etape}) : {self.get_statut_display()}"

