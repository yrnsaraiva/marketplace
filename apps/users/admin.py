from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ['email', 'username', 'papel', 'bloqueado', 'date_joined']
    list_filter = ['papel', 'bloqueado', 'email_verificado']
    fieldsets = UserAdmin.fieldsets + (
        ('Dados adicionais', {
            'fields': ('telefone', 'foto_perfil', 'provincia', 'cidade',
                       'papel', 'bloqueado', 'motivo_bloqueio',
                       'telefone_verificado', 'email_verificado')
        }),
    )