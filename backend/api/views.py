from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
# from django.db import connection

from .models import Entite, User, Profil, CategorieEmploye, Destination, Bareme, Direction, Workflow, UserWorkflow, \
    Mission, MissionWorkflow
from .pagination import MyPagination
from .serializers import RegisterSerializer, LoginSerializer, EntiteSerializer, UserSerializer, ProfilSerializer, \
    CategorieEmployeSerializer, DestinationSerializer, BaremeGetSerializer, BaremePostSerializer, \
    DirectionPostSerializer, DirectionGetSerializer, WorkflowGetSerializer, WorkflowPostSerializer, \
    UserWorkflowGetSerializer, UserWorkflowPostSerializer, MissionPostSerializer, MissionGetSerlializer, \
    MissionGetWorkflowSerializer, MissionPostWorkflowSerializer, UserCreateSerializer, UserUpdateSerializer


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
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                token, _ = Token.objects.get_or_create(user=user)
                response = dict(message="Login success",
                                user=dict(username=username, last_name=user.last_name, first_name=user.first_name,
                                          email_sender=user.email_reciever, token=str(token.key)))
                return Response(response, status=status.HTTP_200_OK)
            else:
                return Response(dict(message="Nom d'utilisateur ou mot de passe incorrect."),
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = User.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = UserSerializer(result_page, many=True)
        total_items = paginator.page.paginator.count
        page_size = paginator.page.paginator.per_page
        total_pages = (total_items + page_size - 1) // page_size
        response = dict(
            data=serializer.data,
            message="Liste des Utilisateurs",
            pagination=dict(
                count=total_items,
                total_pages=total_pages,
                current_page=paginator.page.number,
                page_size=page_size
            )
        )
        # print(connection.queries)
        return paginator.get_paginated_response(response)

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
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().order_by('id')
        serializer = UserSerializer(users, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des Utilisateurs"
        )
        # print(connection.queries)
        return Response(response)


class EntiteView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Entite.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = EntiteSerializer(result_page, many=True)
        total_items = paginator.page.paginator.count
        page_size = paginator.page.paginator.per_page
        total_pages = (total_items + page_size - 1) // page_size
        response = dict(
            data=serializer.data,
            message="Liste des Entités",
            pagination=dict(
                count=total_items,
                total_pages=total_pages,
                current_page=paginator.page.number,
                page_size=page_size
            )
        )
        return paginator.get_paginated_response(response)

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
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Profil.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = ProfilSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des Profils"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = ProfilSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Profil créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class ProfilAllView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Profil.objects.all().order_by('id')
        serializer = ProfilSerializer(queryset, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des Profils"
        )
        return Response(response, status=status.HTTP_200_OK)


class CategorieEmployeView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = CategorieEmploye.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = CategorieEmployeSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des categorie"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = CategorieEmployeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Catégorie employé créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class CategorieAllEmployeView(APIView):
    # permission_classes = [IsAuthenticated]

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
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = DestinationSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des destinations"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = DestinationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Destination créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class BaremeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Bareme.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = BaremeGetSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des barèmes"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = BaremePostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Barème créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class BaremeDetailView(APIView):
    # permission_classes = [IsAuthenticated]

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
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Direction.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = DirectionGetSerializer(result_page, many=True)
        total_items = paginator.page.paginator.count
        page_size = paginator.page.paginator.per_page
        total_pages = (total_items + page_size - 1) // page_size
        response = dict(
            data=serializer.data,
            message="Liste des directions",
            pagination=dict(
                count=total_items,
                total_pages=total_pages,
                current_page=paginator.page.number,
                page_size=page_size
            )
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = DirectionPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Direction créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class DirectionAllView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request):
        directions = Direction.objects.all().order_by('id')
        serializer = DirectionGetSerializer(directions, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des directions",

        )
        return Response(response)


class DirectionDetailView(APIView):
    # permission_classes = [IsAuthenticated]

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
    # permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Workflow.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = WorkflowGetSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des workflows"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = WorkflowPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Worflow créé avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de la création."},
                        status=status.HTTP_400_BAD_REQUEST)


class UserWorkflowView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = UserWorkflow.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = UserWorkflowGetSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des users assigné workflow"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = UserWorkflowPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Utilisateur assigné au workflow avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de l'assignation."},
                        status=status.HTTP_400_BAD_REQUEST)


class MissionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Mission.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = MissionGetSerlializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des missions"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = MissionPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Mission créée avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de création."},
                        status=status.HTTP_400_BAD_REQUEST)


class MissionWorkflowView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Mission.objects.all().order_by('id')
        paginator = MyPagination()
        result_page = paginator.paginate_queryset(queryset, request)
        serializer = MissionGetWorkflowSerializer(result_page, many=True)
        response = dict(
            data=serializer.data,
            message="Liste des missions avec workflow"
        )
        return paginator.get_paginated_response(response)

    def post(self, request):
        serializer = MissionPostWorkflowSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            response = dict(message="Workflow de la mission créé avec success", data=serializer.data)
            return Response(response, status=status.HTTP_201_CREATED)
        return Response({"errors": serializer.errors, "messages": "Echec de création."},
                        status=status.HTTP_400_BAD_REQUEST)
