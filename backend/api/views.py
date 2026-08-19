from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404, render
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Sum
# from django.db import connection

from .permissions import HasMissionAccess, IsSignataire, IsTresorier, IsComptable, IsAdministrateur, NOM_COMPTABLE, _est_admin
from .notifications import (
    notifier_creation_mission, notifier_ajout_delegation,
    notifier_traitement_mission, notifier_paiement,
    notifier_justification_complete, notifier_validation_comptable,
    _envoyer_otp,
)

from .models import Entite, User, Profil, CategorieEmploye, Destination, Bareme, Direction, Workflow, \
    Mission, MissionWorkflow, Delegation, Paiement, JustificationHebergement, PieceJustificative, NotificationLog
from .serializers import RegisterSerializer, LoginSerializer, EntiteSerializer, UserSerializer, ProfilSerializer, \
    CategorieEmployeSerializer, DestinationSerializer, BaremeGetSerializer, BaremePostSerializer, \
    DirectionPostSerializer, DirectionGetSerializer, WorkflowGetSerializer, WorkflowPostSerializer, \
    MissionPostSerializer, MissionGetSerlializer, \
    MissionGetWorkflowSerializer, MissionPostWorkflowSerializer, TraiterMissionSerializer, \
    DelegationGetSerializer, DelegationPostSerializer, PaiementGetSerializer, PaiementPostSerializer, \
    JustificationHebergementSerializer, PieceJustificativePostSerializer, \
    UserCreateSerializer, UserUpdateSerializer, AdminPasswordUpdateSerializer


class RegisterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            response = dict(message="Utilisateur créé avec success")
            return Response(response, status=status.HTTP_201_CREATED)
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


class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = User.objects.all().order_by('id')
        serializer = UserSerializer(queryset, many=True)
        return Response({"message": "Liste des Utilisateurs", "data": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Utilisateur créé avec succès",
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
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user)
        return Response(
            dict(message="Détail de l'utilisateur", data=serializer.data),
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        user.delete()

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
        user = get_object_or_404(User, pk=pk)
        delegations = Delegation.objects.filter(
            employe=user,
            est_longue_duree=False,
            montant_hebergement__gt=0,
            mission__statut_mission__in=['APPROUVEE', 'TERMINEE']
        ).select_related('mission', 'mission__destination_mission').prefetch_related(
            'justification_hebergement__pieces'
        )

        problemes = []
        for d in delegations:
            try:
                total = d.justification_hebergement.pieces.aggregate(
                    total=Sum('montant')
                )['total'] or 0
                if total < d.montant_hebergement:
                    problemes.append({
                        'delegation_id': d.pk,
                        'mission': d.mission.numero_mission,
                        'objet_mission': d.mission.objet_mission,
                        'montant_hebergement': d.montant_hebergement,
                        'montant_justifie': total,
                        'reste_a_justifier': d.montant_hebergement - total,
                    })
            except JustificationHebergement.DoesNotExist:
                problemes.append({
                    'delegation_id': d.pk,
                    'mission': d.mission.numero_mission,
                    'objet_mission': d.mission.objet_mission,
                    'montant_hebergement': d.montant_hebergement,
                    'montant_justifie': 0,
                    'reste_a_justifier': d.montant_hebergement,
                })

        return Response({
            'est_bloque': len(problemes) > 0,
            'message': (
                f"{len(problemes)} hébergement(s) non justifié(s) en attente."
                if problemes else "Aucun blocage."
            ),
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
        entite.delete()

        return Response(
            {
                "message": "Entité supprimée avec succès"
            },
            status=status.HTTP_204_NO_CONTENT
        )


class ProfilView(APIView):
    permission_classes = [AllowAny]

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
    permission_classes = [IsAuthenticated]

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
        destination.delete()
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
        bareme.delete()

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
        direction.delete()

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
        workflow.delete()
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
        if demandeur_id and not _est_admin(request.user):
            delegations_non_justifiees = Delegation.objects.filter(
                employe_id=demandeur_id,
                est_longue_duree=False,
                montant_hebergement__gt=0,
                mission__statut_mission__in=['APPROUVEE', 'TERMINEE']
            ).prefetch_related('justification_hebergement__pieces')

            for d in delegations_non_justifiees:
                try:
                    total = d.justification_hebergement.pieces.aggregate(
                        total=Sum('montant')
                    )['total'] or 0
                    if total < d.montant_hebergement:
                        return Response(
                            {"message": "Vous avez des frais d'hébergement non justifiés. Veuillez les justifier avant de soumettre une nouvelle mission."},
                            status=status.HTTP_403_FORBIDDEN
                        )
                except JustificationHebergement.DoesNotExist:
                    return Response(
                        {"message": "Vous avez des frais d'hébergement non justifiés. Veuillez les justifier avant de soumettre une nouvelle mission."},
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
        mission.delete()
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

        serializer = TraiterMissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        nouveau_statut = serializer.validated_data['statut']
        commentaire = serializer.validated_data.get('commentaire', '')

        etape.statut = nouveau_statut
        etape.commentaire = commentaire
        etape.date_validation = timezone.now()
        etape.user_validation = request.user
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
        user = request.user

        if not _est_admin(user):
            est_demandeur = mission.demandeur_id == user.pk
            est_signataire_de_la_mission = MissionWorkflow.objects.filter(
                mission=mission, workflow__user=user
            ).exists()
            filiale_id = getattr(mission.entite, 'pk', None)
            filiales_ids = list(user.filiales_attribuees.values_list('pk', flat=True))
            est_tresorier_ou_comptable = filiale_id in filiales_ids

            if not (est_demandeur or est_signataire_de_la_mission or est_tresorier_ou_comptable):
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
        delegation.delete()
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
        piece.delete()
        return Response(
            {"message": "Pièce supprimée"},
            status=status.HTTP_204_NO_CONTENT
        )


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

        etapes_en_attente = MissionWorkflow.objects.filter(
            user_validation=user,
            statut='EN_ATTENTE'
        ).select_related('mission')

        missions_a_traiter = [
            etape for etape in etapes_en_attente
            if not MissionWorkflow.objects.filter(
                mission=etape.mission,
                numero_etape__lt=etape.numero_etape
            ).exclude(statut='APPROUVE').exists()
        ]

        serializer = MissionGetWorkflowSerializer(missions_a_traiter, many=True)
        return Response(
            {"message": "Missions à traiter", "data": serializer.data},
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
