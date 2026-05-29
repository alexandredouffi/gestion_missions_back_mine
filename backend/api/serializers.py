from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Entite, Profil, CategorieEmploye, Destination, Bareme, Direction, Workflow, \
    MissionWorkflow, Mission, Delegation, Paiement, JustificationHebergement, PieceJustificative

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
    filiales_attribuees = EntiteSerializer(many=True, read_only=True)
    statut = serializers.BooleanField(source='is_active', read_only=True)
    statut_admin = serializers.SerializerMethodField()
    groupes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'matricule', 'fonction', 'date_naissance', 'telephone', 'email_reciever',
                  'filiale', 'profil', 'category', 'direction', 'filiales_attribuees', 'statut_admin', 'statut',
                  'groupes', 'first_name', 'last_name')

    def get_groupes(self, obj):
        return [group.name for group in obj.groups.all()]

    def get_statut_admin(self, obj):
        return obj.is_staff or obj.is_superuser


class BaremePostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bareme
        fields = ('categorie', 'destination', 'hebergement', 'perdiem', 'communication', 'transport', 'forfait',
                  'longue_duree', 'filiale')


class BaremeGetSerializer(serializers.ModelSerializer):
    categorie = CategorieEmployeSerializer(read_only=True)
    destination = DestinationSerializer(read_only=True)
    filiale = EntiteSerializer(read_only=True)

    class Meta:
        model = Bareme
        fields = ('id', 'filiale', 'categorie', 'destination', 'hebergement', 'perdiem', 'communication', 'transport', 'forfait',
                  'longue_duree')


class WorkflowGetSerializer(serializers.ModelSerializer):
    filiale = EntiteSerializer(read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Workflow
        fields = ('id', 'filiale', 'numero_etape', 'libelle_etape', 'user')


class WorkflowPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = '__all__'


class MissionGetSerlializer(serializers.ModelSerializer):
    entite = EntiteSerializer(read_only=True)
    demandeur = UserSerializer(read_only=True)
    destination_mission = DestinationSerializer(read_only=True)
    class Meta:
        model = Mission
        fields = ('id', 'date_demande', 'entite', 'objet_mission', 'date_depart', 'date_retour', 'lieu_mission',
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
    user_validation = UserSerializer(read_only=True)
    statut_label = serializers.CharField(source='get_statut_display', read_only=True)

    class Meta:
        model = MissionWorkflow
        fields = ('id', 'mission', 'numero_etape', 'libelle_etape', 'user_validation', 'statut', 'statut_label', 'date_validation', 'commentaire')


class MissionPostWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MissionWorkflow
        fields = ('mission', 'workflow', 'user_validation', 'statut', 'date_validation', 'commentaire')


class TraiterMissionSerializer(serializers.Serializer):
    statut = serializers.ChoiceField(choices=['APPROUVE', 'REJETE'])
    commentaire = serializers.CharField(required=False, allow_blank=True)


class DelegationGetSerializer(serializers.ModelSerializer):
    employe = UserSerializer(read_only=True)
    bareme = BaremeGetSerializer(read_only=True)

    class Meta:
        model = Delegation
        fields = (
            'id', 'employe', 'est_chef', 'bareme',
            'duree', 'est_longue_duree',
            'montant_hebergement', 'montant_perdiem',
            'montant_communication', 'montant_transport',
            'montant_total',
        )


class DelegationPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Delegation
        fields = ('mission', 'employe', 'est_chef')


class PaiementGetSerializer(serializers.ModelSerializer):
    delegation = DelegationGetSerializer(read_only=True)

    class Meta:
        model = Paiement
        fields = ('id', 'delegation', 'mode', 'montant', 'reference_cheque', 'cheque_document', 'date_paiement', 'effectue')


class PaiementPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ('delegation', 'mode', 'montant', 'reference_cheque', 'cheque_document', 'date_paiement')

    def validate(self, attrs):
        delegation = attrs['delegation']
        mission = delegation.mission

        if mission.statut_mission != 'APPROUVEE':
            raise serializers.ValidationError("La mission doit être approuvée avant tout paiement.")

        if attrs['montant'] != delegation.montant_total:
            raise serializers.ValidationError(
                f"Le montant doit être égal au total calculé : {delegation.montant_total}."
            )

        if attrs['mode'] == 'CHEQUE':
            if not attrs.get('reference_cheque'):
                raise serializers.ValidationError("La référence du chèque est obligatoire pour un paiement par chèque.")
            if not attrs.get('cheque_document'):
                raise serializers.ValidationError("Le scan du chèque est obligatoire pour un paiement par chèque.")

        return attrs

    def create(self, validated_data):
        paiement = super().create(validated_data)
        paiement.effectue = True
        paiement.save()
        return paiement


class PieceJustificativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJustificative
        fields = ('id', 'libelle', 'montant', 'document', 'date_ajout')
        read_only_fields = ('date_ajout',)


class JustificationHebergementSerializer(serializers.ModelSerializer):
    pieces = PieceJustificativeSerializer(many=True, read_only=True)
    montant_total_justifie = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    montant_attendu = serializers.DecimalField(source='delegation.montant_hebergement', max_digits=12, decimal_places=2, read_only=True)
    est_complet = serializers.BooleanField(read_only=True)
    valide_par_comptable = serializers.SerializerMethodField()

    class Meta:
        model = JustificationHebergement
        fields = ('id', 'delegation', 'date_soumission', 'montant_attendu', 'montant_total_justifie',
                  'est_complet', 'valide_par_comptable', 'date_validation_comptable', 'pieces')
        read_only_fields = ('date_soumission', 'date_validation_comptable')

    def get_valide_par_comptable(self, obj):
        if not obj.valide_par_comptable:
            return None
        u = obj.valide_par_comptable
        return {'id': u.id, 'nom': f'{u.last_name} {u.first_name}'}


class PieceJustificativePostSerializer(serializers.ModelSerializer):
    class Meta:
        model = PieceJustificative
        fields = ('justification', 'libelle', 'montant', 'document')


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    filiales_attribuees = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Entite.objects.all(), required=False
    )

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
            'direction',
            'filiales_attribuees',
        )

    def create(self, validated_data):
        filiales = validated_data.pop('filiales_attribuees', [])
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.filiales_attribuees.set(filiales)
        return user


class AdminPasswordUpdateSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=8)


class UserUpdateSerializer(serializers.ModelSerializer):
    filiales_attribuees = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Entite.objects.all(), required=False
    )

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
            'direction',
            'filiales_attribuees',
        )

    def update(self, instance, validated_data):
        filiales = validated_data.pop('filiales_attribuees', None)
        instance = super().update(instance, validated_data)
        if filiales is not None:
            instance.filiales_attribuees.set(filiales)
        return instance