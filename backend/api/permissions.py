from rest_framework.permissions import BasePermission

NOM_SIGNATAIRE = 'Signataire'
NOM_TRESORIER = 'Trésorier'
NOM_COMPTABLE = 'Comptable'
NOM_ADMINISTRATEUR = 'Administrateur'
PROFILS_AVEC_ACCES_MISSION = ['Utilisateur classique', 'Comptable', 'Signataire', 'Trésorier']


def _est_admin(user):
    return user.is_staff or user.is_superuser or _profil_nom(user) == NOM_ADMINISTRATEUR


def _profil_nom(user):
    return user.profil.nom if user.profil else None


class HasMissionAccess(BasePermission):
    """Tout utilisateur authentifié avec un profil mission (classique, comptable, signataire, trésorier)."""
    message = "Votre profil ne vous donne pas accès à la gestion des missions."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if _est_admin(request.user):
            return True
        return _profil_nom(request.user) in PROFILS_AVEC_ACCES_MISSION


class IsSignataire(BasePermission):
    """Seuls les Signataires (et admins) peuvent valider des missions."""
    message = "Seul un Signataire peut approuver ou rejeter une mission."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if _est_admin(request.user):
            return True
        return _profil_nom(request.user) == NOM_SIGNATAIRE


class IsTresorier(BasePermission):
    """Seuls les Trésoriers (et admins) peuvent enregistrer des paiements."""
    message = "Seul un Trésorier peut enregistrer un paiement."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if _est_admin(request.user):
            return True
        return _profil_nom(request.user) == NOM_TRESORIER


class IsComptable(BasePermission):
    """Seuls les Comptables (et admins) ont accès aux justificatifs de toutes les missions."""
    message = "Seul un Comptable peut consulter les justificatifs de toutes les missions."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if _est_admin(request.user):
            return True
        return _profil_nom(request.user) == NOM_COMPTABLE


class IsAdministrateur(BasePermission):
    """Seuls les Administrateurs (et admins Django) peuvent gérer les référentiels (Entité, Direction, Barème, Workflow)."""
    message = "Seul un Administrateur peut gérer les référentiels."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if _est_admin(request.user):
            return True
        return _profil_nom(request.user) == NOM_ADMINISTRATEUR


# ── Suppléance de signature ─────────────────────────────────────────────────

def peut_traiter_etape(user, etape):
    """
    Détermine si `user` peut traiter l'étape de workflow `etape`.

    Seule compte l'assignation : être désigné sur l'étape (ou suppléer celui qui
    l'est) autorise à signer, y compris si l'on est demandeur de la mission ou
    membre de sa délégation — c'est la présence dans le circuit qui fait foi.

    Retourne (autorise: bool, suppleance: Suppleance|None, motif_refus: str|None).
    La suppléance retournée doit être enregistrée sur l'étape pour la traçabilité.
    """
    from .models import Suppleance

    if not user or not user.is_authenticated:
        return False, None, "Authentification requise."

    # Le signataire désigné
    if etape.user_validation_id == user.pk:
        return True, None, None

    # Un suppléant en cours de mandat
    suppleance = Suppleance.resoudre(etape.user_validation_id, user)
    if suppleance is not None:
        return True, suppleance, None

    if _est_admin(user):
        return True, None, None

    return False, None, (
        "Cette étape est assignée à un autre signataire. "
        "Une suppléance en cours est nécessaire pour agir à sa place."
    )


def suppleances_en_cours(user):
    """Suppléances dont `user` est le suppléant et dont le mandat court en ce moment."""
    from django.utils import timezone
    from .models import Suppleance

    maintenant = timezone.now()
    return Suppleance.objects.filter(
        suppleant=user, active=True,
        date_debut__lte=maintenant, date_fin__gte=maintenant,
    ).select_related('titulaire')


def signataires_representes(user):
    """
    Ids des signataires que `user` représente : lui-même, plus les titulaires
    qu'il supplée en ce moment. Base commune à l'accès en lecture et au droit
    de traiter, pour que les deux ne divergent pas.
    """
    return [user.pk] + list(
        suppleances_en_cours(user).values_list('titulaire_id', flat=True))


def filtre_etapes_accessibles(user):
    """
    Q filtrant les étapes que `user` peut traiter : les siennes, plus l'intégralité
    de celles des titulaires qu'il supplée en ce moment. Coïncide exactement avec
    ce que `peut_traiter_etape` autorise.
    """
    from django.db.models import Q

    return Q(user_validation__in=signataires_representes(user))


def peut_consulter_mission(user, mission):
    """
    Accès en lecture au dossier d'une mission (délégation, paiements…).

    Ouvert au demandeur, aux signataires du circuit — y compris via suppléance —,
    aux comptables et trésoriers de la filiale, et aux admins.
    """
    from .models import MissionWorkflow

    if _est_admin(user):
        return True

    if mission.demandeur_id == user.pk:
        return True

    # On interroge user_validation (le signataire figé sur l'étape) et non
    # workflow.user : le modèle d'étape peut avoir changé ou avoir été supprimé.
    if MissionWorkflow.objects.filter(
        mission=mission, user_validation__in=signataires_representes(user)
    ).exists():
        return True

    return user.filiales_attribuees.filter(pk=mission.entite_id).exists()


# ── Blocage pour hébergement payé non régularisé ────────────────────────────

MOTIFS_BLOCAGE = {
    'NON_JUSTIFIE': "Hébergement payé mais aucune justification déposée",
    'JUSTIFICATION_INCOMPLETE': "Justification incomplète : le montant déposé "
                                "ne couvre pas l'hébergement payé",
    'ATTENTE_VALIDATION_COMPTABLE': "Justification complète mais pas encore "
                                    "validée par le comptable",
}


def dossiers_bloquants(user):
    """
    Délégations de `user` dont l'hébergement a été **payé** sans être régularisé :
    justification absente, incomplète, ou non validée par le comptable.

    Source unique de la règle de blocage : utilisée aussi bien pour la consultation
    (`UtilisateurBlocageView`) que pour l'interdiction d'ajout à une mission.
    """
    from django.db.models import Sum
    from .models import Delegation

    delegations = Delegation.objects.filter(
        employe=user,
        est_longue_duree=False,
        montant_hebergement__gt=0,
        mission__statut_mission__in=['APPROUVEE', 'TERMINEE'],
        paiement__effectue=True,
    ).select_related(
        'mission', 'mission__destination_mission', 'paiement'
    ).prefetch_related('justification_hebergement__pieces')

    problemes = []
    for d in delegations:
        justification = getattr(d, 'justification_hebergement', None)

        if justification is None:
            motif, total, validee = 'NON_JUSTIFIE', 0, False
        else:
            total = justification.pieces.aggregate(total=Sum('montant'))['total'] or 0
            validee = justification.valide_par_comptable is not None
            if total < d.montant_hebergement:
                motif = 'JUSTIFICATION_INCOMPLETE'
            elif not validee:
                motif = 'ATTENTE_VALIDATION_COMPTABLE'
            else:
                continue                  # payé, justifié et validé : rien à signaler

        problemes.append({
            'delegation_id': d.pk,
            'mission': d.mission.numero_mission,
            'objet_mission': d.mission.objet_mission,
            'montant_hebergement': d.montant_hebergement,
            'montant_justifie': total,
            'reste_a_justifier': d.montant_hebergement - total,
            'motif': motif,
            'motif_label': MOTIFS_BLOCAGE[motif],
            'justification_id': justification.pk if justification else None,
            'justification_validee': validee,
            'montant_paye': d.paiement.montant,
            'date_paiement': d.paiement.date_paiement,
        })
    return problemes


def resume_blocage(problemes):
    """Compte les dossiers bloquants par motif."""
    resume = {}
    for p in problemes:
        resume[p['motif']] = resume.get(p['motif'], 0) + 1
    return resume
