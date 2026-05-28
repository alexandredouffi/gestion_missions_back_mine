from django.contrib import admin
from .models import (
    User, Entite, Profil, CategorieEmploye, Destination, Bareme, Direction,
    Mission, Workflow, UserWorkflow, MissionWorkflow
)

# Admin simples
admin.site.register(User)
admin.site.register(Entite)
admin.site.register(Profil)
admin.site.register(CategorieEmploye)
admin.site.register(Destination)
admin.site.register(Bareme)
admin.site.register(Direction)

# Admin personnalisés

@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    readonly_fields = ('numero_mission',)  # numéro généré automatiquement
    list_display = ('numero_mission', 'objet_mission', 'entite', 'statut_mission', 'date_demande')
    list_filter = ('statut_mission', 'entite')
    search_fields = ('numero_mission', 'objet_mission')

@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ('filiale', 'numero_etape', 'libelle_etape')
    list_filter = ('filiale',)
    search_fields = ('libelle_etape',)

@admin.register(UserWorkflow)
class UserWorkflowAdmin(admin.ModelAdmin):
    list_display = ('user', 'workflow')
    list_filter = ('workflow', 'user')
    search_fields = ('user__username', 'workflow__libelle_etape')

@admin.register(MissionWorkflow)
class MissionWorkflowAdmin(admin.ModelAdmin):
    list_display = ('mission', 'workflow', 'user_validation', 'statut', 'date_validation')
    list_filter = ('statut', 'mission')
    search_fields = ('mission__numero_mission', 'user_validation__username')
