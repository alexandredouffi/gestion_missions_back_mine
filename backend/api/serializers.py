from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Entite, Profil, CategorieEmploye, Destination, Bareme, Direction, Workflow, UserWorkflow, \
    MissionWorkflow, Mission

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'matricule', 'fonction', 'date_naissance', 'telephone',
                  'email_reciever', 'filiale', 'profil', 'category', 'direction')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Les mots de passe ne correspondent pas.'})
        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            matricule=validated_data.get('matricule', 'Inconnu'),
            fonction=validated_data.get('fonction', 'Inconnu'),
            date_naissance=validated_data.get('date_naissance', '1900-01-01'),
            telephone=validated_data.get('telephone', 'Inconnu'),
            email_reciever=validated_data.get('email_reciever', 'Inconnu'),
            filiale=validated_data.get('filiale', 'Inconnu'),
            profil=validated_data.get('profil', 'Inconnu'),
            category=validated_data.get('category', 'Inconnu'),
            direction=validated_data.get('category', 'direction')
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class LoginSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password')


class EntiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entite
        fields = '__all__'


class ProfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profil
        fields = '__all__'


class CategorieEmployeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategorieEmploye
        fields = '__all__'


class DestinationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Destination
        fields = '__all__'


class DirectionGetSerializer(serializers.ModelSerializer):
    filiale = EntiteSerializer(read_only=True)

    class Meta:
        model = Direction
        fields = ('id', 'nom', 'filiale', 'description')


class DirectionPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    filiale = EntiteSerializer(read_only=True)
    profil = ProfilSerializer(read_only=True)
    category = CategorieEmployeSerializer(read_only=True)
    direction = DirectionGetSerializer(read_only=True)
    statut = serializers.BooleanField(source='is_active', read_only=True)
    statut_admin = serializers.SerializerMethodField()
    groupes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'matricule', 'fonction', 'date_naissance', 'telephone', 'email_reciever',
                  'filiale', 'profil', 'category', 'direction', 'statut_admin', 'statut', 'groupes', 'first_name',
                  'last_name')

    def get_groupes(self, obj):
        return [group.name for group in obj.groups.all()]

    def get_statut_admin(self, obj):
        return obj.is_staff or obj.is_superuser


class BaremePostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bareme
        fields = ('categorie', 'destination', 'hebergement', 'perdiem', 'communication', 'transport', 'forfait',
                  'longue_duree')


class BaremeGetSerializer(serializers.ModelSerializer):
    categorie = CategorieEmployeSerializer(read_only=True)
    destination = DestinationSerializer(read_only=True)

    class Meta:
        model = Bareme
        fields = ('categorie', 'destination', 'hebergement', 'perdiem', 'communication', 'transport', 'forfait',
                  'longue_duree')


class WorkflowGetSerializer(serializers.ModelSerializer):
    filiale = EntiteSerializer(read_only=True)

    class Meta:
        model = Workflow
        fields = ('filiale', 'numero_etape', 'libelle_etape')


class WorkflowPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = '__all__'


class UserWorkflowGetSerializer(serializers.ModelSerializer):
    workflow = WorkflowGetSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserWorkflow
        fields = ('workflow', 'user')


class UserWorkflowPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWorkflow
        fields = '__all__'


class MissionGetSerlializer(serializers.ModelSerializer):
    entite = EntiteSerializer(read_only=True)
    demandeur = UserSerializer(read_only=True)

    class Meta:
        model = Mission
        fields = ('date_demande', 'entite', 'objet_mission', 'date_depart', 'date_retour', 'lieu_mission',
                  'statut_mission', 'numero_mission', 'destination_mission', 'contexte_mission', 'objectifs_mission',
                  'frais_extra', 'demandeur')


class MissionPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mission
        fields = ('date_demande', 'entite', 'objet_mission', 'date_depart', 'date_retour', 'lieu_mission',
                  'destination_mission', 'contexte_mission', 'objectifs_mission',
                  'frais_extra', 'demandeur')


class MissionGetWorkflowSerializer(serializers.ModelSerializer):
    mission = MissionGetSerlializer(read_only=True)
    worflow = WorkflowGetSerializer(read_only=True)
    user_validation = UserSerializer(read_only=True)

    class Meta:
        model = MissionWorkflow
        fields = ('mission', 'workflow', 'user_validation', 'date_validation', 'statut', 'commentaire')


class MissionPostWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MissionWorkflow
        fields = ('mission', 'workflow', 'date_validation', 'statut', 'commentaire')


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'password',
            'matricule',
            'fonction',
            'date_naissance',
            'telephone',
            'email_reciever',
            'filiale',
            'profil',
            'category',
            'direction'
        )

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'matricule',
            'fonction',
            'date_naissance',
            'telephone',
            'email_reciever',
            'filiale',
            'profil',
            'category',
            'direction'
        )