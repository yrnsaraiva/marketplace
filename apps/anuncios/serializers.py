from rest_framework import serializers
from .models import Anuncio, ImagemAnuncio, AtributoAnuncio, Favorito
from apps.categorias.models import AtributoCategoria
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


# Input para criação de atributos (dentro do payload de criar anúncio)
class AtributoInputSerializer(serializers.Serializer):
    atributo_id = serializers.IntegerField()
    valor = serializers.CharField(max_length=255)


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
    # Atributos dinâmicos — lista de {atributo_id, valor}
    atributos = AtributoInputSerializer(many=True, required=False, write_only=True)
    # ID do PlanoDestaque opcional (compra avulsa no momento de publicar)
    plano_destaque = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Anuncio
        fields = [
            'titulo', 'descricao', 'preco', 'preco_negociavel',
            'condicao', 'categoria', 'provincia', 'cidade',
            'bairro', 'auto_renovar',
            'atributos',     # novo
            'plano_destaque', # novo
        ]

    def validate_categoria(self, value):
        if not value.activa:
            raise serializers.ValidationError('Esta categoria não está disponível.')
        return value

    def validate(self, attrs):
        categoria = attrs.get('categoria')
        atributos_input = attrs.get('atributos', [])

        if categoria:
            atribs_obrigatorios = AtributoCategoria.objects.filter(
                categoria=categoria, obrigatorio=True
            ).values_list('id', flat=True)

            ids_recebidos = {a['atributo_id'] for a in atributos_input}
            em_falta = set(atribs_obrigatorios) - ids_recebidos
            if em_falta:
                nomes = list(
                    AtributoCategoria.objects.filter(id__in=em_falta)
                    .values_list('nome', flat=True)
                )
                raise serializers.ValidationError({
                    'atributos': f'Campos obrigatórios em falta: {", ".join(nomes)}'
                })

        return attrs

    def create(self, validated_data):
        from apps.pagamentos.services import PublicacaoService
        from apps.pagamentos.models import PlanoDestaque, DestaqueAnuncio
        from django.db import transaction

        atributos_data = validated_data.pop('atributos', [])
        plano_destaque_id = validated_data.pop('plano_destaque', None)

        request = self.context['request']
        user = request.user

        with transaction.atomic():
            # Verificar subscrição activa
            service = PublicacaoService(utilizador=user)
            subscricao, erro = service.subscricao_activa()
            if erro:
                raise serializers.ValidationError({'non_field_errors': erro})

            # Criar anúncio
            anuncio = Anuncio.objects.create(
                utilizador=user,
                **validated_data,
            )

            # Guardar atributos
            atribs_validos = {
                a.id: a for a in AtributoCategoria.objects.filter(
                    id__in=[a['atributo_id'] for a in atributos_data],
                    categoria=anuncio.categoria,
                )
            }
            for item in atributos_data:
                atrib = atribs_validos.get(item['atributo_id'])
                if atrib:
                    AtributoAnuncio.objects.create(
                        anuncio=anuncio,
                        atributo=atrib,
                        valor=item['valor'],
                    )

            # Publicar (consome crédito e activa anúncio)
            service.publicar(anuncio)

            # Destaque avulso opcional
            if plano_destaque_id:
                try:
                    plano_destaque = PlanoDestaque.objects.get(
                        pk=plano_destaque_id, activo=True
                    )
                    DestaqueAnuncio.objects.create(
                        anuncio=anuncio,
                        plano_destaque=plano_destaque,
                        origem='compra_avulsa',
                    )
                except PlanoDestaque.DoesNotExist:
                    pass  # ignora silenciosamente — destaque é opcional

            # Actualizar contador no utilizador
            user.total_anuncios = Anuncio.objects.filter(
                utilizador=user
            ).exclude(estado='eliminado').count()
            user.save(update_fields=['total_anuncios'])

        return anuncio


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