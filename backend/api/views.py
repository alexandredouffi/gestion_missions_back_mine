from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404, render
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Sum, Q
from django.db.models.deletion import ProtectedError
# from django.db import connection

from .permissions import HasMissionAccess, IsSignataire, IsTresorier, IsComptable, IsAdministrateur, \
    NOM_COMPTABLE, _est_admin, peut_traiter_etape, filtre_etapes_accessibles, \
    peut_consulter_mission, dossiers_bloquants, resume_blocage
from .notifications import (
    notifier_creation_mission, notifier_ajout_delegation,
    notifier_retrait_delegation, collecter_contexte_retrait_delegation,
    notifier_traitement_mission, notifier_paiement,
    notifier_justification_complete, notifier_validation_comptable, notifier_piece_retiree,
    notifier_lien_mot_de_passe, notifier_suppleance,
    _envoyer_otp, _email,
)

from .models import Entite, User, Profil, CategorieEmploye, Destination, Bareme, Direction, Workflow, \
    Mission, MissionWorkflow, Delegation, Paiement, JustificationHebergement, PieceJustificative, NotificationLog, \
    PasswordSetupToken, Suppleance
from .serializers import RegisterSerializer, LoginSerializer, EntiteSerializer, UserSerializer, ProfilSerializer, \
    CategorieEmployeSerializer, DestinationSerializer, BaremeGetSerializer, BaremePostSerializer, \
    DirectionPostSerializer, DirectionGetSerializer, WorkflowGetSerializer, WorkflowPostSerializer, \
    MissionPostSerializer, MissionGetSerlializer, \
    MissionGetWorkflowSerializer, MissionPostWorkflowSerializer, TraiterMissionSerializer, \
    DelegationGetSerializer, DelegationPostSerializer, PaiementGetSerializer, PaiementPostSerializer, \
    JustificationHebergementSerializer, PieceJustificativePostSerializer, \
    UserCreateSerializer, UserUpdateSerializer, AdminPasswordUpdateSerializer, DefinirMotDePasseSerializer, \
    SuppleanceGetSerializer, SuppleancePostSerializer


def _reponse_protegee(exc, libelle):
    """
    Traduit un ProtectedError en réponse 409 lisible.
    Le champ `blocages` permet au frontend d'expliquer précisément ce qui coince.
    """
    compte = {}
    for obj in exc.protected_objects:
        nom = str(obj._meta.verbose_name)
        compte[nom] = compte.get(nom, 0) + 1

    details = ', '.join(f"{n} {nom}{'s' if n > 1 and not nom.endswith('s') else ''}"
                        for nom, n in sorted(compte.items(), key=lambda x: -x[1]))
    return Response(
        {
            "message": f"Suppression impossible : {libelle} est encore référencé par {details}. "
                       f"Réaffectez ou supprimez ces éléments d'abord.",
            "blocages": compte,
        },
        status=status.HTTP_409_CONFLICT
    )


def _refus_si_bloque(employe):
    """
    Réponse 409 si `employe` a un hébergement payé non régularisé, sinon None.
    Un utilisateur bloqué ne peut pas être envoyé en nouvelle mission.
    """
    problemes = dossiers_bloquants(employe)
    if not problemes:
        return None

    return Response(
        {
            "message": (
                f"{employe.username} ne peut pas être ajouté à une mission : "
                f"{len(problemes)} hébergement(s) payé(s) non régularisé(s). "
                f"Ces dossiers doivent être justifiés et validés par le comptable."
            ),
            "est_bloque": True,
            "resume": resume_blocage(problemes),
            "delegations_non_justifiees": problemes,
        },
        status=status.HTTP_409_CONFLICT
    )


def _paiements_de_mission(mission):
    """Paiements enregistrés sur les délégations d'une mission."""
    return Paiement.objects.filter(delegation__mission=mission)


def envoyer_lien_mot_de_passe(user, motif='CREATION'):
    """Génère un lien à usage unique et l'envoie par email. Retourne le token créé."""
    jeton = PasswordSetupToken.generer(user, motif=motif)
    duree = int((jeton.expires_at - jeton.created_at).total_seconds() // 3600)
    notifier_lien_mot_de_passe(user, jeton.construire_url(), duree, motif=motif)
    return jeton


class RegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            lien_envoye = False
            if not user.has_usable_password():
                envoyer_lien_mot_de_passe(user, motif='CREATION')
                lien_envoye = True
            return Response(
                {
                    "message": (
                        "Utilisateur créé. Un lien de définition du mot de passe lui a été envoyé par email."
                        if lien_envoye else "Utilisateur créé avec success"
                    ),
                    "lien_mot_de_passe_envoye": lien_envoye,
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        try:
            raw_user = User.objects.get(username=username)
            if not raw_user.is_active:
                return Response(
                    {"message": "Ce compte est désactivé. Contactez un administrateur."},
                    status=status.HTTP_403_FORBIDDEN
                )
            if not raw_user.has_usable_password():
                return Response(
                    {
                        "message": "Votre mot de passe n'a pas encore été défini. "
                                   "Consultez le lien d'activation envoyé à votre adresse email.",
                        "mot_de_passe_a_definir": True,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
        except User.DoesNotExist:
            pass

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"message": "Nom d'utilisateur ou mot de passe incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .models import OTPCode
        otp = OTPCode.generer(user)
        _envoyer_otp(user, otp.code)

        return Response(
            {"message": "Code OTP envoyé à votre adresse email.", "user_id": user.id, "otp_required": True},
            status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        code = str(request.data.get('code', '')).strip().zfill(6)

        if not user_id or not code or code == '000000':
            return Response(
                {"message": "user_id et code sont requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, pk=user_id)

        if not user.is_active:
            return Response(
                {"message": "Ce compte est désactivé."},
                status=status.HTTP_403_FORBIDDEN
            )

        from .models import OTPCode
        try:
            otp = OTPCode.objects.filter(user=user, code=code, is_used=False).latest('created_at')
        except OTPCode.DoesNotExist:
            return Response(
                {"message": "Code OTP invalide."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not otp.est_valide:
            return Response(
                {"message": "Code OTP expiré. Veuillez vous reconnecter pour en recevoir un nouveau (valable 5 minutes)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save(update_fields=['is_used'])

        refresh = RefreshToken.for_user(user)
        return Response(
            dict(
                message="Connexion réussie.",
                user=dict(
                    username=user.username,
                    id=user.id,
                    last_name=user.last_name,
                    first_name=user.first_name,
                    email_sender=user.email_reciever,
                    profil=dict(
                        id=user.profil.id,
                        nom=user.profil.nom,
                    ) if user.profil else None,
                    is_admin=user.is_staff or user.is_superuser,
                ),
                access=str(refresh.access_token),
                refresh=str(refresh),
            ),
            status=status.HTTP_200_OK
        )


class DefinirMotDePasseView(APIView):
    """Consultation et consommation d'un lien de définition de mot de passe."""
    permission_classes = [AllowAny]

    def _recuperer(self, token):
        try:
            return PasswordSetupToken.objects.select_related('user').get(token=token)
        except PasswordSetupToken.DoesNotExist:
            return None

    def get(self, request, token):
        jeton = self._recuperer(token)
        if jeton is None:
            return Response(
                {"message": "Lien invalide.", "valide": False},
                status=status.HTTP_404_NOT_FOUND
            )
        if not jeton.est_valide:
            motif = "déjà utilisé" if jeton.is_used else "expiré"
            return Response(
                {"message": f"Ce lien est {motif}. Demandez-en un nouveau à un administrateur.",
                 "valide": False},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not jeton.user.is_active:
            return Response(
                {"message": "Ce compte est désactivé. Contactez un administrateur.", "valide": False},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {
                "valide": True,
                "username": jeton.user.username,
                "nom_complet": f"{jeton.user.last_name} {jeton.user.first_name}".strip(),
                "expire_le": jeton.expires_at,
            },
            status=status.HTTP_200_OK
        )

    def post(self, request, token):
        jeton = self._recuperer(token)
        if jeton is None:
            return Response({"message": "Lien invalide."}, status=status.HTTP_404_NOT_FOUND)
        if not jeton.est_valide:
            motif = "déjà utilisé" if jeton.is_used else "expiré"
            return Response(
                {"message": f"Ce lien est {motif}. Demandez-en un nouveau à un administrateur."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not jeton.user.is_active:
            return Response(
                {"message": "Ce compte est désactivé. Contactez un administrateur."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = DefinirMotDePasseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        user = jeton.user
        user.set_password(serializer.validated_data['password'])
        user.save(update_fields=['password'])
        jeton.marquer_utilise()

        return Response(
            {"message": "Mot de passe défini avec succès. Vous pouvez maintenant vous connecter.",
             "username": user.username},
            status=status.HTTP_200_OK
        )


class RenvoyerLienMotDePasseView(APIView):
    """Renvoi par un administrateur du lien de définition de mot de passe."""
    permission_classes = [IsAdministrateur]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if not user.is_active:
            return Response(
                {"message": "Ce compte est désactivé. Réactivez-le avant d'envoyer un lien."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not _email(user):
            return Response(
                {"message": "Cet utilisateur n'a pas d'adresse email valide."},
                status=status.HTTP_400_BAD_REQUEST
            )

        motif = 'CREATION' if not user.has_usable_password() else 'REINITIALISATION'
        jeton = envoyer_lien_mot_de_passe(user, motif=motif)
        return Response(
            {"message": "Lien envoyé par email.", "expire_le": jeton.expires_at},
            status=status.HTTP_200_OK
        )


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = User.objects.all().order_by('id')
        serializer = UserSerializer(queryset, many=True)
        return Response({"message": "Liste des Utilisateurs", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            lien_envoye = False
            if not user.has_usable_password():
                envoyer_lien_mot_de_passe(user, motif='CREATION')
                lien_envoye = True
            return Response(
                {
                    "message": (
                        "Utilisateur créé avec succès. Un lien de définition du mot de passe "
                        "lui a été envoyé par email."
                        if lien_envoye else "Utilisateur créé avec succès"
                    ),
                    "lien_mot_de_passe_envoye": lien_envoye,
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            {
                "errors": serializer.errors,
                "message": "Échec de la création de l’utilisateur"
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class UserDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)
        return Response(
            dict(message="Détail de l'utilisateur", data=serializer.data),
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        try:
            user.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"l'utilisateur « {user.username} »")

        return Response(
            {
                "message": "Utilisateur supprimé avec succès"
            },
            status=status.HTTP_204_NO_CONTENT
        )

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        print(request.data)
        serializer = UserUpdateSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Utilisateur mis à jour avec succès", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class UserAllView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().order_by('id')
        serializer = UserSerializer(users, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des Utilisateurs"
        )
        # print(connection.queries)
        return Response(response)


class AdminPasswordUpdateView(APIView):
    permission_classes = [IsAdministrateur]

    def put(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = AdminPasswordUpdateSerializer(data=request.data)
        if serializer.is_valid():
            user.set_password(serializer.validated_data['password'])
            user.save()
            return Response({"message": "Mot de passe mis à jour avec succès."}, status=status.HTTP_200_OK)
        return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class UserStatutView(APIView):
    permission_classes = [IsAdministrateur]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        etat = "activé" if user.is_active else "désactivé"
        return Response(
            {"message": f"Utilisateur {etat} avec succès.", "statut": user.is_active},
            status=status.HTTP_200_OK
        )


class UtilisateurBlocageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """
        Un utilisateur est bloqué dès qu'un hébergement lui a été **payé** sans
        que la justification correspondante soit déposée, complète et validée
        par le comptable.
        """
        user = get_object_or_404(User, pk=pk)
        problemes = dossiers_bloquants(user)

        return Response({
            'est_bloque': len(problemes) > 0,
            'message': (
                f"{len(problemes)} hébergement(s) payé(s) non régularisé(s)."
                if problemes else "Aucun blocage."
            ),
            'resume': resume_blocage(problemes),
            'delegations_non_justifiees': problemes,
        }, status=status.HTTP_200_OK)


class EntiteView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request):
        queryset = Entite.objects.all().order_by('id')
        serializer = EntiteSerializer(queryset, many=True)
        return Response({"message": "Liste des Entités", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = EntiteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Entité créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class EntiteAllList(APIView):
    def get(self, request):
        entites = Entite.objects.all().order_by('id')
        serializer = EntiteSerializer(entites, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des Entités",
        )
        return Response(response, status=status.HTTP_200_OK)


class EntiteDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        entite = get_object_or_404(Entite, pk=pk)
        serializer = EntiteSerializer(entite)
        return Response(
            {
                "message": "Détail de l’entité",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        entite = get_object_or_404(Entite, pk=pk)
        serializer = EntiteSerializer(entite, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Entité mise à jour avec succès",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "errors": serializer.errors,
                "message": "Échec de la mise à jour"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request, pk):
        entite = get_object_or_404(Entite, pk=pk)
        serializer = EntiteSerializer(entite, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Entité mise à jour partiellement",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "errors": serializer.errors,
                "message": "Échec de la mise à jour partielle"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        entite = get_object_or_404(Entite, pk=pk)
        try:
            entite.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"l'entité « {entite.nom} »")

        return Response(
            {
                "message": "Entité supprimée avec succès"
            },
            status=status.HTTP_204_NO_CONTENT
        )


class ProfilView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Profil.objects.all().order_by('id')
        serializer = ProfilSerializer(queryset, many=True)
        return Response({"message": "Liste des Profils", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ProfilSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Profil créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class ProfilAllView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Profil.objects.all().order_by('id')
        serializer = ProfilSerializer(queryset, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des Profils"
        )
        return Response(response, status=status.HTTP_200_OK)


class CategorieEmployeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = CategorieEmploye.objects.all().order_by('id')
        serializer = CategorieEmployeSerializer(queryset, many=True)
        return Response({"message": "Liste des categorie", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CategorieEmployeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Catégorie employé créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class CategorieAllEmployeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = CategorieEmploye.objects.all().order_by('id')
        serializer = CategorieEmployeSerializer(queryset, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des categorie"
        )
        return Response(response, status=status.HTTP_200_OK)


class DestinationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Destination.objects.all().order_by('id')
        serializer = DestinationSerializer(queryset, many=True)
        return Response({"message": "Liste des destinations", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = DestinationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Destination créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class DestinationAllView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        destinations = Destination.objects.all().order_by('id')
        serializer = DestinationSerializer(destinations, many=True)
        return Response(
            {"message": "Liste des destinations", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class DestinationDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        destination = get_object_or_404(Destination, pk=pk)
        serializer = DestinationSerializer(destination)
        return Response(
            {"message": "Détail de la destination", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        destination = get_object_or_404(Destination, pk=pk)
        serializer = DestinationSerializer(destination, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Destination mise à jour avec succès", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec de la mise à jour"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        destination = get_object_or_404(Destination, pk=pk)
        try:
            destination.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"la destination « {destination.nom} »")
        return Response(
            {"message": "Destination supprimée avec succès"},
            status=status.HTTP_204_NO_CONTENT
        )


class BaremeView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request):
        queryset = Bareme.objects.all().order_by('id')
        serializer = BaremeGetSerializer(queryset, many=True)
        return Response({"message": "Liste des barèmes", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = BaremePostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Barème créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class BaremeDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        bareme = get_object_or_404(Bareme, pk=pk)
        serializer = BaremeGetSerializer(bareme)
        return Response(
            {
                "message": "Détail du barème",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        bareme = get_object_or_404(Bareme, pk=pk)
        serializer = BaremePostSerializer(bareme, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Barème mis à jour avec succès",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "errors": serializer.errors,
                "message": "Échec de la mise à jour"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        bareme = get_object_or_404(Bareme, pk=pk)
        try:
            bareme.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"le barème #{bareme.pk}")

        return Response(
            {
                "message": "Barème supprimé avec succès"
            },
            status=status.HTTP_204_NO_CONTENT
        )


class DirectionView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request):
        queryset = Direction.objects.all().order_by('id')
        serializer = DirectionGetSerializer(queryset, many=True)
        return Response({"message": "Liste des directions", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = DirectionPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Direction créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class DirectionAllView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        directions = Direction.objects.all().order_by('id')
        serializer = DirectionGetSerializer(directions, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des directions",

        )
        return Response(response)


class DirectionDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        direction = get_object_or_404(Direction, pk=pk)
        serializer = DirectionGetSerializer(direction)
        return Response(
            {
                "message": "Détail de la direction",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        direction = get_object_or_404(Direction, pk=pk)
        serializer = DirectionPostSerializer(direction, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Direction mis à jour avec succès",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "errors": serializer.errors,
                "message": "Échec de la mise à jour"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        direction = get_object_or_404(Direction, pk=pk)
        try:
            direction.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"la direction « {direction.nom} »")

        return Response(
            {
                "message": "Direction supprimé avec succès"
            },
            status=status.HTTP_204_NO_CONTENT
        )


class DirectionDetailByFilialeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, filiale):
        # direction = get_object_or_404(Direction, filiale=filiale)
        direction = Direction.objects.filter(filiale=filiale).order_by('id')
        serializer = DirectionGetSerializer(direction, many=True)
        return Response(
            {
                "message": "Détail de la direction",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )


class WorflowView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request):
        queryset = Workflow.objects.all().order_by('id')
        serializer = WorkflowGetSerializer(queryset, many=True)
        return Response({"message": "Liste des workflows", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WorkflowPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Worflow créé avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class WorkflowDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAdministrateur()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        workflow = get_object_or_404(Workflow, pk=pk)
        serializer = WorkflowGetSerializer(workflow)
        return Response(
            {"message": "Détail du workflow", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        workflow = get_object_or_404(Workflow, pk=pk)
        serializer = WorkflowPostSerializer(workflow, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Workflow mis à jour avec succès", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec de la mise à jour"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        workflow = get_object_or_404(Workflow, pk=pk)
        try:
            workflow.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"l'étape « {workflow.libelle_etape} »")
        return Response(
            {"message": "Workflow supprimé avec succès"},
            status=status.HTTP_204_NO_CONTENT
        )


class MissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Mission.objects.all().order_by('id')
        serializer = MissionGetSerlializer(queryset, many=True)
        return Response({"message": "Liste des missions", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        demandeur_id = request.data.get('demandeur')
        if demandeur_id:
            demandeur = get_object_or_404(User, pk=demandeur_id)
            problemes = dossiers_bloquants(demandeur)
            if problemes:
                return Response(
                    {
                        "message": "Vous avez des frais d'hébergement payés non "
                                   "régularisés. Ils doivent être justifiés et validés "
                                   "par le comptable avant de soumettre une nouvelle mission.",
                        "est_bloque": True,
                        "resume": resume_blocage(problemes),
                        "delegations_non_justifiees": problemes,
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = MissionPostSerializer(data=request.data)
        if serializer.is_valid():
            mission = serializer.save()
            notifier_creation_mission(mission)
            return Response(
                {"message": "Mission créée avec success", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response({"errors": serializer.errors, "messages": "Echec de création."},
                        status=status.HTTP_400_BAD_REQUEST)


class MissionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)
        serializer = MissionGetSerlializer(mission)
        return Response(
            {"message": "Détail de la mission", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)

        if mission.statut_mission == 'APPROUVEE' and not _est_admin(request.user):
            return Response(
                {"message": "Impossible de modifier une mission déjà approuvée."},
                status=status.HTTP_403_FORBIDDEN
            )

        etait_rejetee = mission.statut_mission == 'REJETEE'

        serializer = MissionPostSerializer(mission, data=request.data)
        if serializer.is_valid():
            serializer.save()

            if etait_rejetee:
                mission.statut_mission = 'EN_ATTENTE'
                mission.save()
                MissionWorkflow.objects.filter(mission=mission).update(
                    statut='EN_ATTENTE',
                    date_validation=None,
                    commentaire=None,
                )

            for delegation in mission.delegations.select_related('employe__filiale', 'employe__category'):
                delegation.bareme = None
                delegation.save()

            return Response(
                {"message": "Mission mise à jour avec succès", "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec de la mise à jour"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)

        if not _est_admin(request.user) and mission.demandeur_id != request.user.pk:
            return Response(
                {"message": "Seul le demandeur de la mission ou un administrateur "
                            "peut la supprimer."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Supprimer la mission détruit ses délégations, donc les paiements
        # et justifications associés. On refuse dès qu'un paiement existe.
        paiements = _paiements_de_mission(mission)
        if paiements.exists():
            return Response(
                {
                    "message": f"Suppression impossible : {paiements.count()} paiement(s) "
                               f"sont enregistrés sur cette mission. Supprimez-les d'abord.",
                    "paiements": [
                        {
                            "delegation_id": p.delegation_id,
                            "employe": p.delegation.employe.username,
                            "montant": p.montant,
                            "effectue": p.effectue,
                        }
                        for p in paiements.select_related('delegation__employe')
                    ],
                },
                status=status.HTTP_409_CONFLICT
            )

        try:
            mission.delete()
        except ProtectedError as exc:
            return _reponse_protegee(exc, f"la mission {mission.numero_mission}")

        return Response(
            {"message": "Mission supprimée avec succès"},
            status=status.HTTP_204_NO_CONTENT
        )


class MissionParUtilisateurView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        queryset = Mission.objects.filter(demandeur=user).order_by('-date_demande')
        serializer = MissionGetSerlializer(queryset, many=True)
        return Response({"message": "Missions de l'utilisateur", "data": serializer.data}, status=status.HTTP_200_OK)


class MissionDelegationUtilisateurView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        queryset = Mission.objects.filter(
            delegations__employe=user
        ).distinct().order_by('-date_demande')
        serializer = MissionGetSerlializer(queryset, many=True)
        return Response({"message": "Missions de la délégation de l'utilisateur", "data": serializer.data}, status=status.HTTP_200_OK)


class TraiterMissionView(APIView):
    permission_classes = [IsSignataire]

    def put(self, request, pk):
        etape = get_object_or_404(MissionWorkflow, pk=pk)

        if etape.statut != 'EN_ATTENTE':
            return Response(
                {"message": "Cette étape a déjà été traitée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        etapes_precedentes_non_approuvees = MissionWorkflow.objects.filter(
            mission=etape.mission,
            numero_etape__lt=etape.numero_etape
        ).exclude(statut='APPROUVE').exists()

        if etapes_precedentes_non_approuvees:
            return Response(
                {"message": "Les étapes précédentes ne sont pas encore approuvées."},
                status=status.HTTP_400_BAD_REQUEST
            )

        autorise, suppleance, motif = peut_traiter_etape(request.user, etape)
        if not autorise:
            return Response({"message": motif}, status=status.HTTP_403_FORBIDDEN)

        serializer = TraiterMissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        nouveau_statut = serializer.validated_data['statut']
        commentaire = serializer.validated_data.get('commentaire', '')

        etape.statut = nouveau_statut
        etape.commentaire = commentaire
        etape.date_validation = timezone.now()
        # user_validation reste le signataire DÉSIGNÉ : on ne l'écrase jamais.
        etape.traite_par = request.user
        etape.suppleance = suppleance
        etape.save()

        mission = etape.mission
        if nouveau_statut == 'REJETE':
            mission.statut_mission = 'REJETEE'
            mission.save()
        elif nouveau_statut == 'APPROUVE':
            toutes_approuvees = not MissionWorkflow.objects.filter(
                mission=mission
            ).exclude(statut='APPROUVE').exists()
            if toutes_approuvees:
                mission.statut_mission = 'APPROUVEE'
                mission.save()

        notifier_traitement_mission(etape, request.user)

        return Response(
            {"message": "Mission traitée avec succès", "data": MissionGetWorkflowSerializer(etape).data},
            status=status.HTTP_200_OK
        )


class MissionWorkflowView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Mission.objects.all().order_by('id')
        serializer = MissionGetWorkflowSerializer(queryset, many=True)
        return Response({"message": "Liste des missions avec workflow", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = MissionPostWorkflowSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Workflow de la mission créé avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de création."},
                        status=status.HTTP_400_BAD_REQUEST)


class DelegationMissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)

        if not peut_consulter_mission(request.user, mission):
            return Response(
                {"message": "Vous n'êtes pas autorisé à consulter cette délégation."},
                status=status.HTTP_403_FORBIDDEN
            )

        delegations = Delegation.objects.filter(mission=mission).select_related('employe', 'bareme')
        serializer = DelegationGetSerializer(delegations, many=True)
        return Response(
            {"message": "Membres de la délégation", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def post(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)
        data = request.data.copy()
        data['mission'] = mission.pk
        serializer = DelegationPostSerializer(data=data)
        if serializer.is_valid():
            refus = _refus_si_bloque(serializer.validated_data['employe'])
            if refus is not None:
                return refus

            delegation = serializer.save()
            notifier_ajout_delegation(delegation)
            return Response(
                {"message": "Membre ajouté à la délégation", "data": DelegationGetSerializer(delegation).data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec de l'ajout"},
            status=status.HTTP_400_BAD_REQUEST
        )


class DelegationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        delegation = get_object_or_404(Delegation, pk=pk)
        serializer = DelegationGetSerializer(delegation)
        return Response(
            {"message": "Détail du membre", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        delegation = get_object_or_404(Delegation, pk=pk)
        serializer = DelegationPostSerializer(delegation, data=request.data)
        if serializer.is_valid():
            # Contrôle uniquement si l'on change de bénéficiaire : sinon toute
            # modification d'une délégation existante deviendrait impossible.
            nouvel_employe = serializer.validated_data.get('employe')
            if nouvel_employe and nouvel_employe.pk != delegation.employe_id:
                refus = _refus_si_bloque(nouvel_employe)
                if refus is not None:
                    return refus

            delegation = serializer.save()
            return Response(
                {"message": "Membre mis à jour", "data": DelegationGetSerializer(delegation).data},
                status=status.HTTP_200_OK
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec de la mise à jour"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, pk):
        delegation = get_object_or_404(Delegation, pk=pk)
        delegation.est_chef = True
        delegation.save()
        return Response(
            {"message": "Chef de délégation mis à jour", "data": DelegationGetSerializer(delegation).data},
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        delegation = get_object_or_404(Delegation, pk=pk)

        # Retirer un membre détruit en cascade son paiement et sa justification.
        paiement = getattr(delegation, 'paiement', None)
        if paiement is not None:
            return Response(
                {
                    "message": f"Suppression impossible : un paiement de "
                               f"{paiement.montant:,.0f} F CFA est enregistré pour "
                               f"{delegation.employe.username}. Supprimez-le d'abord.",
                    "paiement": {
                        "id": paiement.pk,
                        "mode": paiement.mode,
                        "montant": paiement.montant,
                        "effectue": paiement.effectue,
                    },
                },
                status=status.HTTP_409_CONFLICT
            )

        contexte = collecter_contexte_retrait_delegation(delegation)

        delegation.delete()
        notifier_retrait_delegation(contexte, request.user)

        return Response(
            {"message": "Membre retiré de la délégation"},
            status=status.HTTP_204_NO_CONTENT
        )


class PaiementMissionView(APIView):

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsTresorier()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)
        paiements = Paiement.objects.filter(
            delegation__mission=mission
        ).select_related('delegation__employe')
        serializer = PaiementGetSerializer(paiements, many=True)
        return Response(
            {"message": "Paiements de la mission", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def post(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)

        user = request.user
        if not _est_admin(user):
            if not user.filiales_attribuees.filter(pk=mission.entite_id).exists():
                return Response(
                    {"message": "Vous n'êtes pas autorisé à enregistrer un paiement pour cette filiale."},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = PaiementPostSerializer(data=request.data)
        if serializer.is_valid():
            paiement = serializer.save()
            paiement.enregistre_par = request.user
            paiement.save(update_fields=['enregistre_par'])
            notifier_paiement(paiement, request.user)
            return Response(
                {"message": "Paiement enregistré", "data": PaiementGetSerializer(paiement).data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec du paiement"},
            status=status.HTTP_400_BAD_REQUEST
        )


class PaiementDetailView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        paiement = get_object_or_404(Paiement, pk=pk)
        serializer = PaiementGetSerializer(paiement)
        return Response(
            {"message": "Détail du paiement", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class OrdreMissionPrintView(APIView):
    permission_classes = [HasMissionAccess]

    def get(self, request, pk):
        delegation = get_object_or_404(
            Delegation.objects.select_related(
                'mission', 'mission__entite', 'mission__destination_mission',
                'employe', 'employe__direction', 'employe__category', 'bareme'
            ),
            pk=pk
        )
        if delegation.mission.statut_mission != 'APPROUVEE':
            return Response(
                {"message": "L'ordre de mission n'est disponible que pour les missions approuvées."},
                status=status.HTTP_403_FORBIDDEN
            )
        etapes = MissionWorkflow.objects.filter(
            mission=delegation.mission
        ).select_related('user_validation').order_by('numero_etape')
        return render(request, 'api/ordre_mission.html', {'delegation': delegation, 'etapes': etapes})


class FichePaiePrintView(APIView):
    permission_classes = [HasMissionAccess]

    def get(self, request, pk):
        paiement = get_object_or_404(
            Paiement.objects.select_related(
                'delegation__mission', 'delegation__mission__entite',
                'delegation__mission__destination_mission',
                'delegation__employe', 'delegation__employe__direction',
                'delegation__bareme'
            ),
            pk=pk
        )
        if not paiement.effectue:
            return Response(
                {"message": "La fiche de paiement n'est disponible qu'après paiement effectué."},
                status=status.HTTP_403_FORBIDDEN
            )
        etapes = MissionWorkflow.objects.filter(
            mission=paiement.delegation.mission
        ).select_related('user_validation').order_by('numero_etape')
        return render(request, 'api/fiche_paie.html', {'paiement': paiement, 'etapes': etapes})




class JustificationHebergementView(APIView):
    permission_classes = [IsAuthenticated]

    def _est_comptable(self, user):
        return _est_admin(user) or (user.profil and user.profil.nom == NOM_COMPTABLE)

    def _comptable_autorise_filiale(self, user, delegation):
        if _est_admin(user):
            return True
        return user.filiales_attribuees.filter(pk=delegation.mission.entite_id).exists()

    def get(self, request, pk):
        delegation = get_object_or_404(Delegation, pk=pk)
        if self._est_comptable(request.user):
            if not self._comptable_autorise_filiale(request.user, delegation):
                return Response(
                    {"message": "Vous n'êtes pas autorisé à consulter les justifications de cette filiale."},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif delegation.employe != request.user:
            return Response(
                {"message": "Vous n'êtes pas autorisé à consulter cette justification."},
                status=status.HTTP_403_FORBIDDEN
            )
        justification, _ = JustificationHebergement.objects.get_or_create(delegation=delegation)
        serializer = JustificationHebergementSerializer(justification)
        return Response(
            {"message": "Justification hébergement", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    def post(self, request, pk):
        delegation = get_object_or_404(Delegation, pk=pk)
        if self._est_comptable(request.user):
            if not self._comptable_autorise_filiale(request.user, delegation):
                return Response(
                    {"message": "Vous n'êtes pas autorisé à créer une justification pour cette filiale."},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif delegation.employe != request.user:
            return Response(
                {"message": "Vous ne pouvez créer une justification que pour votre propre délégation."},
                status=status.HTTP_403_FORBIDDEN
            )
        if hasattr(delegation, 'justification_hebergement'):
            return Response(
                {"message": "Une justification existe déjà pour cette délégation."},
                status=status.HTTP_400_BAD_REQUEST
            )
        justification = JustificationHebergement.objects.create(delegation=delegation)
        serializer = JustificationHebergementSerializer(justification)
        return Response(
            {"message": "Justification créée", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )


class PieceJustificativeView(APIView):
    # permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        justification = get_object_or_404(JustificationHebergement, pk=pk)
        data = request.data.copy()
        data['justification'] = justification.pk
        serializer = PieceJustificativePostSerializer(data=data)
        if serializer.is_valid():
            piece = serializer.save()
            justification.refresh_from_db()
            if justification.est_complet and not justification.valide_par_comptable:
                notifier_justification_complete(justification)
            from .serializers import PieceJustificativeSerializer
            return Response(
                {"message": "Pièce ajoutée", "data": PieceJustificativeSerializer(piece).data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"errors": serializer.errors, "message": "Échec de l'ajout"},
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, pk):
        piece = get_object_or_404(PieceJustificative, pk=pk)
        justification = piece.justification
        etait_complete = justification.est_complet
        libelle, montant = piece.libelle, piece.montant

        piece.delete()
        justification.refresh_from_db()
        notifier_piece_retiree(justification, libelle, montant, request.user, etait_complete)

        return Response(
            {"message": "Pièce supprimée"},
            status=status.HTTP_204_NO_CONTENT
        )


class SuppleanceView(APIView):
    """Déclarer une absence et consulter les suppléances."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        ?role=accordees  → les suppléances que j'ai accordées (mes absences)
        ?role=recues     → celles dont je suis le suppléant
        ?titulaire=<pk>  → admin uniquement
        défaut           → les deux me concernant
        """
        role = request.query_params.get('role')
        titulaire = request.query_params.get('titulaire')

        if titulaire:
            if not _est_admin(request.user):
                return Response(
                    {"message": "Réservé aux administrateurs."},
                    status=status.HTTP_403_FORBIDDEN
                )
            qs = Suppleance.objects.filter(titulaire_id=titulaire)
        elif role == 'accordees':
            qs = Suppleance.objects.filter(titulaire=request.user)
        elif role == 'recues':
            qs = Suppleance.objects.filter(suppleant=request.user)
        else:
            qs = Suppleance.objects.filter(
                Q(titulaire=request.user) | Q(suppleant=request.user))

        qs = qs.select_related('titulaire', 'suppleant', 'cree_par')
        return Response(
            {"message": "Suppléances", "data": SuppleanceGetSerializer(qs, many=True).data},
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """Le titulaire déclare son absence ; un admin peut le faire à sa place."""
        data = request.data.copy()
        data.setdefault('titulaire', request.user.pk)

        if str(data['titulaire']) != str(request.user.pk) and not _est_admin(request.user):
            return Response(
                {"message": "Vous ne pouvez déclarer une absence que pour vous-même."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SuppleancePostSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors, "message": "Échec de la création"},
                status=status.HTTP_400_BAD_REQUEST
            )

        suppleance = serializer.save(cree_par=request.user)
        notifier_suppleance(suppleance, request.user, evenement='CREATION')
        return Response(
            {"message": "Suppléance enregistrée. Le suppléant a été prévenu.",
             "data": SuppleanceGetSerializer(suppleance).data},
            status=status.HTTP_201_CREATED
        )


class SuppleanceDetailView(APIView):
    """Fin anticipée ou annulation d'une suppléance."""
    permission_classes = [IsAuthenticated]

    def _autorise(self, request, suppleance):
        return _est_admin(request.user) or suppleance.titulaire_id == request.user.pk

    def patch(self, request, pk):
        """Retour anticipé : la suppléance cesse immédiatement."""
        suppleance = get_object_or_404(Suppleance, pk=pk)
        if not self._autorise(request, suppleance):
            return Response(
                {"message": "Seul le titulaire ou un administrateur peut mettre fin "
                            "à cette suppléance."},
                status=status.HTTP_403_FORBIDDEN
            )
        if not suppleance.active:
            return Response(
                {"message": "Cette suppléance est déjà terminée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        suppleance.terminer()
        notifier_suppleance(suppleance, request.user, evenement='FIN')
        return Response(
            {"message": "Suppléance terminée.",
             "data": SuppleanceGetSerializer(suppleance).data},
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        """Annule une suppléance qui n'a encore rien traité."""
        suppleance = get_object_or_404(Suppleance, pk=pk)
        if not self._autorise(request, suppleance):
            return Response(
                {"message": "Seul le titulaire ou un administrateur peut supprimer "
                            "cette suppléance."},
                status=status.HTTP_403_FORBIDDEN
            )

        nb = suppleance.etapes_traitees.count()
        if nb:
            return Response(
                {"message": f"Suppression impossible : {nb} étape(s) ont été traitées "
                            f"sous cette suppléance. Utilisez PATCH pour y mettre fin "
                            f"en conservant l'historique."},
                status=status.HTTP_409_CONFLICT
            )

        suppleance.delete()
        return Response({"message": "Suppléance supprimée."},
                        status=status.HTTP_204_NO_CONTENT)


class EtapesMissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mission = get_object_or_404(Mission, pk=pk)
        etapes = MissionWorkflow.objects.filter(mission=mission).order_by('numero_etape')
        serializer = MissionGetWorkflowSerializer(etapes, many=True)
        return Response(
            {"message": "Étapes de la mission", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class MissionsJustifieesComptableView(APIView):
    permission_classes = [IsComptable]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        filiales = user.filiales_attribuees.all()

        missions_approuvees = Mission.objects.filter(
            statut_mission='APPROUVEE',
            entite__in=filiales
        ).prefetch_related(
            'delegations__justification_hebergement__pieces'
        )

        missions_completes = []
        for mission in missions_approuvees:
            delegations_avec_heberg = [
                d for d in mission.delegations.all()
                if not d.est_longue_duree and d.montant_hebergement > 0
            ]
            if not delegations_avec_heberg:
                continue
            for d in delegations_avec_heberg:
                try:
                    justif = d.justification_hebergement
                    total = justif.pieces.aggregate(total=Sum('montant'))['total'] or 0
                    if total >= d.montant_hebergement:
                        missions_completes.append(mission)
                        break
                except JustificationHebergement.DoesNotExist:
                    continue

        serializer = MissionGetSerlializer(missions_completes, many=True)
        return Response({"message": "Missions avec justifications complètes", "data": serializer.data}, status=status.HTTP_200_OK)



class ValidationComptableView(APIView):
    permission_classes = [IsComptable]

    def patch(self, request, pk):
        justification = get_object_or_404(JustificationHebergement, pk=pk)

        if not _est_admin(request.user):
            if not request.user.filiales_attribuees.filter(
                pk=justification.delegation.mission.entite_id
            ).exists():
                return Response(
                    {"message": "Vous n'êtes pas autorisé à valider les justifications de cette filiale."},
                    status=status.HTTP_403_FORBIDDEN
                )

        if not justification.est_complet:
            return Response(
                {"message": "La justification n'est pas encore complète."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if justification.valide_par_comptable:
            return Response(
                {"message": "Cette justification a déjà été validée."},
                status=status.HTTP_400_BAD_REQUEST
            )

        justification.valide_par_comptable = request.user
        justification.date_validation_comptable = timezone.now()
        justification.save(update_fields=['valide_par_comptable', 'date_validation_comptable'])
        notifier_validation_comptable(justification, request.user)

        return Response(
            {"message": "Justification validée par le comptable.", "data": JustificationHebergementSerializer(justification).data},
            status=status.HTTP_200_OK
        )


class MissionAPayerView(APIView):
    permission_classes = [IsTresorier]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        filiales = user.filiales_attribuees.all()
        queryset = Mission.objects.filter(
            statut_mission='APPROUVEE',
            entite__in=filiales
        ).order_by('-date_demande')
        serializer = MissionGetSerlializer(queryset, many=True)
        return Response({"message": "Missions à payer", "data": serializer.data}, status=status.HTTP_200_OK)


class MissionATraiterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        # Ses propres étapes, plus celles des titulaires qu'il supplée en ce moment.
        etapes_en_attente = MissionWorkflow.objects.filter(
            filtre_etapes_accessibles(user),
            statut='EN_ATTENTE'
        ).select_related('mission', 'user_validation')

        missions_a_traiter = [
            etape for etape in etapes_en_attente
            if not MissionWorkflow.objects.filter(
                mission=etape.mission,
                numero_etape__lt=etape.numero_etape
            ).exclude(statut='APPROUVE').exists()
        ]

        serializer = MissionGetWorkflowSerializer(missions_a_traiter, many=True)
        data = serializer.data

        # Marque les lignes que l'utilisateur traiterait au titre d'une suppléance.
        for ligne, etape in zip(data, missions_a_traiter):
            en_suppleance = etape.user_validation_id != user.pk
            ligne['a_traiter_en_suppleance'] = en_suppleance
            ligne['titulaire'] = (
                {
                    'id': etape.user_validation.id,
                    'username': etape.user_validation.username,
                    'nom': f'{etape.user_validation.last_name} '
                           f'{etape.user_validation.first_name}'.strip(),
                } if en_suppleance and etape.user_validation else None
            )

        return Response(
            {"message": "Missions à traiter", "data": data},
            status=status.HTTP_200_OK
        )


class DelegationsMissionsASignerView(APIView):
    permission_classes = [IsSignataire]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)

        etapes_en_attente = MissionWorkflow.objects.filter(
            user_validation=user,
            statut='EN_ATTENTE'
        ).select_related('mission')

        missions_a_signer = [
            etape.mission for etape in etapes_en_attente
            if not MissionWorkflow.objects.filter(
                mission=etape.mission,
                numero_etape__lt=etape.numero_etape
            ).exclude(statut='APPROUVE').exists()
        ]

        delegations = Delegation.objects.filter(
            mission__in=missions_a_signer
        ).select_related('employe', 'bareme', 'mission')

        serializer = DelegationGetSerializer(delegations, many=True)
        return Response(
            {"message": "Membres des missions à signer", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class NotificationLogView(APIView):
    permission_classes = [IsAdministrateur]

    def get(self, request):
        logs = NotificationLog.objects.all()[:200]
        data = [
            {
                "id": log.id,
                "sujet": log.sujet,
                "destinataires": log.destinataires,
                "statut": log.statut,
                "erreur": log.erreur,
                "date_envoi": log.date_envoi,
            }
            for log in logs
        ]
        return Response({"message": "Logs des notifications", "data": data}, status=status.HTTP_200_OK)
