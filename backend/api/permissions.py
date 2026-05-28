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
