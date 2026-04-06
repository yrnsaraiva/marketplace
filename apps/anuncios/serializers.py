from rest_framework import serializers
from .models import Anuncio, ImagemAnuncio, AtributoAnuncio, Favorito
from apps.categorias.serializers import CategoriaSimpleSerializer
from apps.users.serializers import PerfilSerializer


class ImagemAnuncioSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ImagemAnuncio
        fields = ['id', 'url', 'ordem', 'principal']

    def get_url(self, obj):
        request = self.context.get('request')
        if obj.imagem and request:
            return request.build_absolute_uri(obj.imagem.url)
        return None


class AtributoAnuncioSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source='atributo.nome', read_only=True)
    chave = serializers.CharField(source='atributo.chave', read_only=True)

    class Meta:
        model = AtributoAnuncio
        fields = ['id', 'nome', 'chave', 'valor']


class AnuncioListSerializer(serializers.ModelSerializer):
    imagem_principal = serializers.SerializerMethodField()
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True)
    utilizador_nome = serializers.CharField(source='utilizador.username', read_only=True)

    class Meta:
        model = Anuncio
        fields = ['id', 'titulo', 'preco', 'preco_negociavel', 'condicao',
                  'provincia', 'cidade', 'estado', 'visualizacoes',
                  'categoria_nome', 'utilizador_nome',
                  'imagem_principal', 'publicado_em']

    def get_imagem_principal(self, obj):
        request = self.context.get('request')
        imagem = obj.imagens.filter(principal=True).first()
        if not imagem:
            imagem = obj.imagens.first()
        if imagem and request:
            return request.build_absolute_uri(imagem.imagem.url)
        return None


class AnuncioDetalheSerializer(serializers.ModelSerializer):
    imagens = ImagemAnuncioSerializer(many=True, read_only=True)
    atributos = AtributoAnuncioSerializer(many=True, read_only=True)
    categoria = CategoriaSimpleSerializer(read_only=True)
    utilizador = PerfilSerializer(read_only=True)

    class Meta:
        model = Anuncio
        fields = ['id', 'titulo', 'descricao', 'preco', 'preco_negociavel',
                  'condicao', 'provincia', 'cidade', 'bairro', 'estado',
                  'visualizacoes', 'contactos_recebidos', 'categoria',
                  'utilizador', 'imagens', 'atributos',
                  'criado_em', 'expira_em']


class AnuncioCriarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anuncio
        fields = ['titulo', 'descricao', 'preco', 'preco_negociavel',
                  'condicao', 'categoria', 'provincia', 'cidade',
                  'bairro', 'auto_renovar']

    def create(self, validated_data):
        validated_data['utilizador'] = self.context['request'].user
        return super().create(validated_data)


class UploadImagensSerializer(serializers.Serializer):
    anuncio_id = serializers.IntegerField()
    imagens = serializers.ListField(
        child=serializers.ImageField(), max_length=10
    )

    def validate_anuncio_id(self, value):
        user = self.context['request'].user
        try:
            anuncio = Anuncio.objects.get(pk=value, utilizador=user)
        except Anuncio.DoesNotExist:
            raise serializers.ValidationError(
                'Anúncio não encontrado ou não pertence a este utilizador.'
            )
        return value


class FavoritoSerializer(serializers.ModelSerializer):
    anuncio = AnuncioListSerializer(read_only=True)

    class Meta:
        model = Favorito
        fields = ['id', 'anuncio', 'criado_em']