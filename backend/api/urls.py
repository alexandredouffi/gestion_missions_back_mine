from django.urls import path
from .views import RegisterView, LoginView, EntiteView, EntiteDetailView, UserView, ProfilView, ProfilAllView, \
    CategorieEmployeView, CategorieAllEmployeView, \
    DestinationView, DirectionView, DirectionDetailView, DirectionDetailByFilialeView, BaremeDetailView, BaremeView, WorflowView, UserWorkflowView, \
    MissionView, MissionWorkflowView, EntiteAllList, UserAllView, DirectionAllView, UserDetailView

urlpatterns = [
    path('inscription/', RegisterView.as_view(), name='inscription'),
    path('authentification/', LoginView.as_view(), name='authentification'),
    path('utilisateur/', UserView.as_view(), name='utilisateur-detail'),
    path('utilisateur/<int:pk>/', UserDetailView.as_view(), name='utilisateur'),
    path('utilisateur/all/', UserAllView.as_view(), name='utilisateur-all'),
    path('entite/', EntiteView.as_view(), name='entite'),
    path('entite/all/', EntiteAllList.as_view(), name='entite-all'),
    path('entite/<int:pk>/', EntiteDetailView.as_view(), name='entite-detail'),
    path('profil/', ProfilView.as_view(), name='profil'),
    path('profil/all/', ProfilAllView.as_view(), name='profil-all'),
    path('categorie-employe/', CategorieEmployeView.as_view(), name='categorie-employe'),
    path('categorie-employe/all/', CategorieAllEmployeView.as_view(), name='categorie-employe-all'),
    path('destination/', DestinationView.as_view(), name='destination'),
    path('bareme/', BaremeView.as_view(), name='bareme'),
    path('bareme/<int:pk>/', BaremeDetailView.as_view(), name='bareme-detail'),
    path('direction/', DirectionView.as_view(), name='direction'),
    path('direction/all/', DirectionAllView.as_view(), name='direction-all'),
    path('direction/<int:pk>/', DirectionDetailView.as_view(), name='direction-detail'),
    path('direction/filiale/<int:filiale>/', DirectionDetailByFilialeView.as_view(), name='direction-all'),
    path('workflow/', WorflowView.as_view(), name='workflow'),
    path('user-workflow/', UserWorkflowView.as_view(), name='user-workflow'),
    path('mission/', MissionView.as_view(), name='mission'),
    path('mission-workflow/', MissionWorkflowView.as_view(), name='mission-workflow'),
]
