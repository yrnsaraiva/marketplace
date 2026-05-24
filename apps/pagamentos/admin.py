from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    PlanoPublicacao,
    SubscricaoUtilizador,
    Pagamento,
    PlanoDestaque,
    DestaqueAnuncio,
)


# ---------------------------------------------------------------------------
# PLANO DE PUBLICAÇÃO
# ---------------------------------------------------------------------------

@admin.register(PlanoPublicacao)
class PlanoPublicacaoAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'tipo', 'preco', 'max_anuncios_display',
        'duracao_anuncio_dias', 'max_imagens', 'dias_destaque_incluidos', 'activo', 'ordem'
    ]
    list_editable = ['activo', 'ordem']
    list_filter = ['tipo', 'activo']
    search_fields = ['nome']

    def max_anuncios_display(self, obj):
        return '∞ Ilimitado' if obj.ilimitado else obj.max_anuncios
    max_anuncios_display.short_description = 'Máx. Anúncios'


# ---------------------------------------------------------------------------
# SUBSCRIÇÃO
# ---------------------------------------------------------------------------

@admin.register(SubscricaoUtilizador)
class SubscricaoUtilizadorAdmin(admin.ModelAdmin):
    list_display = [
        'utilizador', 'plano', 'estado', 'creditos_disponiveis_display',
        'inicio_em', 'expira_em', 'valida_display'
    ]
    list_filter = ['estado', 'plano']
    search_fields = ['utilizador__username', 'utilizador__email']
    readonly_fields = ['criado_em', 'actualizado_em', 'inicio_em', 'expira_em']
    raw_id_fields = ['utilizador']

    def creditos_disponiveis_display(self, obj):
        if obj.ilimitado:
            return '∞'
        return f'{obj.creditos_disponiveis} / {obj.creditos_totais}'
    creditos_disponiveis_display.short_description = 'Créditos'

    def valida_display(self, obj):
        if obj.valida:
            return format_html(
                '<span style="color:green;">{} Válida</span>',
                '✔'
            )

        return format_html(
            '<span style="color:red;">{} Inválida</span>',
            '✘'
        )

    valida_display.short_description = 'Estado'


# ---------------------------------------------------------------------------
# PAGAMENTO
# ---------------------------------------------------------------------------

@admin.action(description='✔ Confirmar pagamentos seleccionados')
def confirmar_pagamentos(modeladmin, request, queryset):
    confirmados = 0
    for pagamento in queryset.filter(estado='pendente'):
        pagamento.confirmar(confirmado_por=request.user)
        confirmados += 1
    modeladmin.message_user(
        request,
        f'{confirmados} pagamento(s) confirmado(s) e subscrição(ões) activada(s).'
    )


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'utilizador_display', 'plano_display', 'valor',
        'metodo', 'estado', 'estado_badge', 'criado_em', 'confirmado_em'
    ]
    list_filter = ['estado', 'metodo', 'criado_em']
    search_fields = [
        'subscricao__utilizador__username',
        'subscricao__utilizador__email',
        'referencia_externa',
        'telefone_pagamento',
    ]
    readonly_fields = [
        'criado_em', 'actualizado_em', 'confirmado_em',
        'confirmado_por', 'resposta_gateway'
    ]
    actions = [confirmar_pagamentos]

    def utilizador_display(self, obj):
        return obj.subscricao.utilizador.username
    utilizador_display.short_description = 'Utilizador'

    def plano_display(self, obj):
        return obj.subscricao.plano.nome
    plano_display.short_description = 'Plano'

    def estado_badge(self, obj):
        cores = {
            'pendente': 'orange',
            'confirmado': 'green',
            'falhado': 'red',
            'reembolsado': 'grey',
        }
        cor = cores.get(obj.estado, 'black')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            cor, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'


# ---------------------------------------------------------------------------
# PLANO DE DESTAQUE
# ---------------------------------------------------------------------------

@admin.register(PlanoDestaque)
class PlanoDestaqueAdmin(admin.ModelAdmin):
    list_display = ['nome', 'tipo', 'preco', 'duracao_dias', 'activo', 'ordem']
    list_editable = ['activo', 'ordem']
    list_filter = ['tipo', 'activo']


# ---------------------------------------------------------------------------
# DESTAQUE ANÚNCIO
# ---------------------------------------------------------------------------

@admin.register(DestaqueAnuncio)
class DestaqueAnuncioAdmin(admin.ModelAdmin):
    list_display = ['anuncio', 'origem', 'plano_destaque', 'inicio_em', 'fim_em', 'activo', 'expirado_display']
    list_filter = ['activo', 'origem']
    search_fields = ['anuncio__titulo']
    readonly_fields = ['inicio_em']

    def expirado_display(self, obj):
        if obj.expirado:
            return format_html(
                '<span style="color:red;">{}</span>',
                'Expirado'
            )
        return format_html(
            '<span style="color:green;">{}</span>',
            'Activo'
        )