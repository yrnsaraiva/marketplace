from django.contrib import admin
from django.utils import timezone

from .models import PlanoDestaque, DestaqueAnuncio


@admin.register(PlanoDestaque)
class PlanoDestaqueAdmin(admin.ModelAdmin):
    list_display = (
        'nome',
        'tipo',
        'preco',
        'duracao_dias',
        'boost_visualizacoes',
        'activo',
    )

    list_filter = (
        'tipo',
        'activo',
    )

    search_fields = (
        'nome',
        'descricao',
    )

    ordering = ('nome',)


@admin.register(DestaqueAnuncio)
class DestaqueAnuncioAdmin(admin.ModelAdmin):
    list_display = (
        'anuncio',
        'plano',
        'inicio_em',
        'fim_em',
        'activo',
        'status_expiracao',
    )

    list_filter = (
        'activo',
        'plano',
        'inicio_em',
        'fim_em',
    )

    search_fields = (
        'anuncio__titulo',
        'plano__nome',
    )

    readonly_fields = (
        'inicio_em',
        'status_expiracao',
    )

    autocomplete_fields = ('anuncio',)

    actions = [
        'ativar_destaques',
        'desativar_destaques',
    ]

    def status_expiracao(self, obj):
        if not obj.fim_em:
            return "Sem data"
        if timezone.now() > obj.fim_em:
            return "Expirado"
        return "Activo"
    status_expiracao.short_description = "Estado"

    def ativar_destaques(self, request, queryset):
        queryset.update(activo=True)
    ativar_destaques.short_description = "Ativar destaques selecionados"

    def desativar_destaques(self, request, queryset):
        queryset.update(activo=False)
    desativar_destaques.short_description = "Desativar destaques selecionados"