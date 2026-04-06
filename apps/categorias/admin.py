from django.contrib import admin
from .models import Categoria, AtributoCategoria


class AtributoCategoriaInline(admin.TabularInline):
    model = AtributoCategoria
    extra = 1


class SubcategoriaInline(admin.TabularInline):
    model = Categoria
    fk_name = 'pai'
    extra = 0
    fields = ['nome', 'slug', 'ordem', 'activa']


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'pai', 'nivel', 'ordem', 'activa']
    list_filter = ['activa', 'nivel']
    search_fields = ['nome', 'slug']
    prepopulated_fields = {'slug': ('nome',)}
    inlines = [SubcategoriaInline, AtributoCategoriaInline]


@admin.register(AtributoCategoria)
class AtributoCategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'categoria', 'tipo', 'obrigatorio']
    list_filter = ['tipo', 'obrigatorio']