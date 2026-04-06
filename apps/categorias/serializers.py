from rest_framework import serializers
from .models import Categoria, AtributoCategoria


class AtributoCategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = AtributoCategoria
        fields = ['id', 'nome', 'chave', 'tipo', 'opcoes', 'obrigatorio']


class SubcategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug', 'icone_url', 'ordem']


class CategoriaSerializer(serializers.ModelSerializer):
    subcategorias = SubcategoriaSerializer(many=True, read_only=True)
    atributos = AtributoCategoriaSerializer(many=True, read_only=True)

    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug', 'icone_url', 'ordem',
                  'nivel', 'subcategorias', 'atributos']


class CategoriaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'slug', 'icone_url', 'ordem']