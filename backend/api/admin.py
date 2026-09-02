from django.contrib import admin
from .models import (
    User, Entite, Profil, CategorieEmploye, Destination, Bareme, Direction,
    Mission, Workflow, MissionWorkflow, PasswordSetupToken, Suppleance
)

admin.site.register(User)
admin.site.register(Entite)
admin.site.register(Profil)
admin.site.register(CategorieEmploye)
admin.site.register(Destination)
admin.site.register(Bareme)
admin.site.register(Direction)


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    readonly_fields = ('numero_mission',)
    list_display = ('numero_mission', 'objet_mission', 'entite', 'statut_mission', 'date_demande')
    list_filter = ('statut_mission', 'entite')
    search_fields = ('numero_mission', 'objet_mission')


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ('filiale', 'numero_etape', 'libelle_etape', 'user')
    list_filter = ('filiale',)
    search_fields = ('libelle_etape', 'user__username')


@admin.register(MissionWorkflow)
class MissionWorkflowAdmin(admin.ModelAdmin):
    list_display = ('mission', 'workflow', 'user_validation', 'statut', 'date_validation')
    list_filter = ('statut', 'mission')
    search_fields = ('mission__numero_mission', 'user_validation__username')


@admin.register(PasswordSetupToken)
class PasswordSetupTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'motif', 'created_at', 'expires_at', 'is_used', 'used_at')
    list_filter = ('motif', 'is_used')
    search_fields = ('user__username', 'user__matricule')
    readonly_fields = ('token', 'created_at', 'used_at')


@admin.register(Suppleance)
class SuppleanceAdmin(admin.ModelAdmin):
    list_display = ('titulaire', 'suppleant', 'date_debut', 'date_fin', 'statut', 'active')
    list_filter = ('active',)
    search_fields = ('titulaire__username', 'suppleant__username')
    readonly_fields = ('created_at',)
