from django.urls import path
from .views import RegisterView, LoginView, EntiteView, EntiteDetailView, UserView, ProfilView, ProfilAllView, \
    NotificationLogView, \
    CategorieEmployeView, CategorieAllEmployeView, \
    DestinationView, DestinationAllView, DestinationDetailView, DirectionView, DirectionDetailView, DirectionDetailByFilialeView, BaremeDetailView, BaremeView, WorflowView, WorkflowDetailView, \
    MissionView, MissionDetailView, MissionParUtilisateurView, MissionDelegationUtilisateurView, MissionWorkflowView, MissionATraiterView, TraiterMissionView, EtapesMissionView, \
    DelegationMissionView, DelegationDetailView, PaiementMissionView, PaiementDetailView, \
    OrdreMissionPrintView, FichePaiePrintView, \
    EntiteAllList, UserAllView, DirectionAllView, UserDetailView, \
    JustificationHebergementView, PieceJustificativeView, UtilisateurBlocageView, AdminPasswordUpdateView, \
    MissionAPayerView, DelegationsMissionsASignerView, UserStatutView, \
    MissionsJustifieesComptableView, ValidationComptableView, VerifyOTPView, \
    DefinirMotDePasseView, RenvoyerLienMotDePasseView, \
    SuppleanceView, SuppleanceDetailView

urlpatterns = [
    path('inscription/', RegisterView.as_view(), name='inscription'),
    path('authentification/', LoginView.as_view(), name='authentification'),
    path('authentification/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('utilisateur/', UserView.as_view(), name='utilisateur-detail'),
    path('utilisateur/<int:pk>/', UserDetailView.as_view(), name='utilisateur'),
    path('utilisateur/all/', UserAllView.as_view(), name='utilisateur-all'),
    path('utilisateur/<int:pk>/blocage/', UtilisateurBlocageView.as_view(), name='utilisateur-blocage'),
    path('utilisateur/<int:pk>/mot-de-passe/', AdminPasswordUpdateView.as_view(), name='utilisateur-mot-de-passe'),
    path('utilisateur/<int:pk>/lien-mot-de-passe/', RenvoyerLienMotDePasseView.as_view(), name='utilisateur-lien-mot-de-passe'),
    path('definir-mot-de-passe/<str:token>/', DefinirMotDePasseView.as_view(), name='definir-mot-de-passe'),
    path('utilisateur/<int:pk>/statut/', UserStatutView.as_view(), name='utilisateur-statut'),
    path('employes/all/', UserAllView.as_view(), name='employes-all'),
    path('entite/', EntiteView.as_view(), name='entite'),
    path('entite/all/', EntiteAllList.as_view(), name='entite-all'),
    path('entite/<int:pk>/', EntiteDetailView.as_view(), name='entite-detail'),
    path('profil/', ProfilView.as_view(), name='profil'),
    path('profil/all/', ProfilAllView.as_view(), name='profil-all'),
    path('categorie-employe/', CategorieEmployeView.as_view(), name='categorie-employe'),
    path('categorie-employe/all/', CategorieAllEmployeView.as_view(), name='categorie-employe-all'),
    path('destination/', DestinationView.as_view(), name='destination'),
    path('destination/all/', DestinationAllView.as_view(), name='destination-all'),
    path('destination/<int:pk>/', DestinationDetailView.as_view(), name='destination-detail'),
    path('bareme/', BaremeView.as_view(), name='bareme'),
    path('bareme/<int:pk>/', BaremeDetailView.as_view(), name='bareme-detail'),
    path('direction/', DirectionView.as_view(), name='direction'),
    path('direction/all/', DirectionAllView.as_view(), name='direction-all'),
    path('direction/<int:pk>/', DirectionDetailView.as_view(), name='direction-detail'),
    path('direction/filiale/<int:filiale>/', DirectionDetailByFilialeView.as_view(), name='direction-all'),
    path('workflow/', WorflowView.as_view(), name='workflow'),
    path('workflow/<int:pk>/', WorkflowDetailView.as_view(), name='workflow-detail'),
    path('mission/', MissionView.as_view(), name='mission'),
    path('mission/<int:pk>/', MissionDetailView.as_view(), name='mission-detail'),
    path('mission/<int:pk>/etapes/', EtapesMissionView.as_view(), name='mission-etapes'),
    path('mission/utilisateur/<int:pk>/', MissionParUtilisateurView.as_view(), name='mission-par-utilisateur'),
    path('mission/delegation/<int:pk>/', MissionDelegationUtilisateurView.as_view(), name='mission-delegation-utilisateur'),
    path('mission/a-traiter/<int:pk>/', MissionATraiterView.as_view(), name='mission-a-traiter'),
    path('delegation/a-signer/<int:pk>/', DelegationsMissionsASignerView.as_view(), name='delegations-a-signer'),
    path('mission/a-payer/<int:pk>/', MissionAPayerView.as_view(), name='mission-a-payer'),
    path('mission/justifiees/<int:pk>/', MissionsJustifieesComptableView.as_view(), name='missions-justifiees-comptable'),
    path('justification/<int:pk>/validation-comptable/', ValidationComptableView.as_view(), name='validation-comptable'),
    path('mission-workflow/', MissionWorkflowView.as_view(), name='mission-workflow'),
    path('mission-workflow/<int:pk>/traiter/', TraiterMissionView.as_view(), name='traiter-mission'),
    path('suppleance/', SuppleanceView.as_view(), name='suppleance'),
    path('suppleance/<int:pk>/', SuppleanceDetailView.as_view(), name='suppleance-detail'),
    path('delegation/mission/<int:pk>/', DelegationMissionView.as_view(), name='delegation-mission'),
    path('delegation/<int:pk>/', DelegationDetailView.as_view(), name='delegation-detail'),
    path('paiement/mission/<int:pk>/', PaiementMissionView.as_view(), name='paiement-mission'),
    path('paiement/<int:pk>/', PaiementDetailView.as_view(), name='paiement-detail'),
    path('impression/ordre-mission/<int:pk>/', OrdreMissionPrintView.as_view(), name='impression-ordre-mission'),
    path('impression/fiche-paie/<int:pk>/', FichePaiePrintView.as_view(), name='impression-fiche-paie'),
    path('justification/delegation/<int:pk>/', JustificationHebergementView.as_view(), name='justification-delegation'),
    path('justification/<int:pk>/piece/', PieceJustificativeView.as_view(), name='piece-justificative-add'),
    path('piece-justificative/<int:pk>/', PieceJustificativeView.as_view(), name='piece-justificative-delete'),
    path('notifications/logs/', NotificationLogView.as_view(), name='notification-logs'),
]
