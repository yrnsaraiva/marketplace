from django.contrib import admin
from .models import Anuncio, ImagemAnuncio, AtributoAnuncio, Favorito


class ImagemAnuncioInline(admin.TabularInline):
    model = ImagemAnuncio
    extra = 0
    readonly_fields = ['criado_em']


class AtributoAnuncioInline(admin.TabularInline):
    model = AtributoAnuncio
    extra = 0


@admin.register(Anuncio)
class AnuncioAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'utilizador', 'categoria', 'preco',
                    'estado', 'visualizacoes', 'criado_em']
    list_filter = ['estado', 'provincia', 'categoria']
    search_fields = ['titulo', 'descricao', 'utilizador__email']
    readonly_fields = ['visualizacoes', 'contactos_recebidos',
                       'criado_em', 'actualizado_em']
    inlines = [ImagemAnuncioInline, AtributoAnuncioInline]
    actions = ['aprovar_anuncios', 'rejeitar_anuncios']

    def aprovar_anuncios(self, request, queryset):
        queryset.update(estado='activo')
    aprovar_anuncios.short_description = 'Aprovar anúncios seleccionados'

    def rejeitar_anuncios(self, request, queryset):
        queryset.update(estado='rejeitado')
    rejeitar_anuncios.short_description = 'Rejeitar anúncios seleccionados'


@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ['utilizador', 'anuncio', 'criado_em']