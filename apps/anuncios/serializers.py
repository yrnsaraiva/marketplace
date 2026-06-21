from rest_framework import serializers
from django.core.validators import MinLengthValidator

from .models import Anuncio, ImagemAnuncio, AtributoAnuncio, Favorito
from apps.categorias.models import AtributoCategoria
from apps.categorias.serializers import CategoriaSimpleSerializer
from apps.users.serializers import PerfilSerializer
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q


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
    destacado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Anuncio
        fields = ['id', 'titulo', 'preco', 'preco_negociavel', 'condicao',
                  'provincia', 'cidade', 'estado', 'visualizacoes',
                  'categoria_nome', 'utilizador_nome',
                  'imagem_principal', 'publicado_em', 'destacado']

    def get_imagem_principal(self, obj):
        request = self.context.get('request')
        imgs = list(obj.imagens.all())
        imagem = next(
            (i for i in imgs if i.principal),
            imgs[0] if imgs else None
        )
        if not imagem:
            return None
        if request:
            return request.build_absolute_uri(imagem.imagem.url)
        return imagem.imagem.url


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


def _validar_atributos_obrigatorios(categoria, atributos_input):
    """
    Reutilizável: valida que todos os atributos obrigatórios da categoria
    foram fornecidos. Lança ValidationError se faltar algum.
    """
    if not categoria:
        return
    obrigatorios = AtributoCategoria.objects.filter(
        categoria=categoria, obrigatorio=True
    ).values_list('id', flat=True)
    ids_recebidos = {a['atributo_id'] for a in atributos_input}
    em_falta = set(obrigatorios) - ids_recebidos
    if em_falta:
        nomes = list(
            AtributoCategoria.objects.filter(id__in=em_falta)
            .values_list('nome', flat=True)
        )
        raise serializers.ValidationError({
            'atributos': f'Campos obrigatórios em falta: {", ".join(nomes)}'
        })


class AnuncioCriarSerializer(serializers.ModelSerializer):
    # Atributos dinâmicos - lista de {atributo_id, valor}
    atributos = AtributoInputSerializer(many=True, required=False, write_only=True)
    destacar = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Anuncio
        fields = [
            'id',
            'titulo', 'descricao', 'preco', 'preco_negociavel',
            'condicao', 'categoria', 'provincia', 'cidade',
            'bairro', 'auto_renovar',
            'atributos', 'destacar',
        ]

    def validate_titulo(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError('O título deve ter pelo menos 10 caracteres.')
        return value

    def validate_categoria(self, value):
        if not value.activa:
            raise serializers.ValidationError('Esta categoria não está disponível.')
        return value

    def validate(self, attrs):
        _validar_atributos_obrigatorios(
            attrs.get('categoria'),
            attrs.get('atributos', [])
        )
        return attrs

    def create(self, validated_data):
        from apps.pagamentos.services import PublicacaoService
        from django.db import transaction
        from apps.pagamentos.models import DestaqueAnuncio
        from django.utils import timezone
        from datetime import timedelta

        atributos_data = validated_data.pop('atributos', [])
        destacar = validated_data.pop('destacar', False)

        request = self.context['request']
        user = request.user

        with transaction.atomic():
            service = PublicacaoService(utilizador=user)
            subscricao, erro = service.subscricao_activa()
            if erro:
                raise serializers.ValidationError({'non_field_errors': erro})

            anuncio = Anuncio.objects.create(
                utilizador=user,
                subscricao=subscricao,
                **validated_data,
            )

            atribs_validos = {
                a.id: a for a in AtributoCategoria.objects.filter(
                    id__in=[a['atributo_id'] for a in atributos_data],
                ).filter(
                    Q(categoria=anuncio.categoria) | Q(categoria=anuncio.categoria.pai)
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

            if destacar:
                dias_destaque = subscricao.plano.dias_destaque_incluidos
                if dias_destaque > 0:
                    DestaqueAnuncio.objects.create(
                        anuncio=anuncio,
                        subscricao=subscricao,
                        fim_em=timezone.now() + timedelta(days=dias_destaque),
                        activo=True
                    )

            service.publicar(anuncio)

            user.total_anuncios = Anuncio.objects.filter(
                utilizador=user
            ).exclude(estado='eliminado').count()
            user.save(update_fields=['total_anuncios'])

        return anuncio


class AnuncioEditarSerializer(serializers.ModelSerializer):
    atributos = AtributoInputSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Anuncio
        fields = [
            'titulo', 'descricao', 'preco', 'preco_negociavel',
            'condicao', 'categoria', 'provincia', 'cidade',
            'bairro', 'auto_renovar', 'atributos',
        ]
        extra_kwargs = {
            'auto_renovar': {'required': False},
        }

    def validate_titulo(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError('O título deve ter pelo menos 10 caracteres.')
        return value

    def validate_categoria(self, value):
        if not value.activa:
            raise serializers.ValidationError('Esta categoria não está disponível.')
        return value

    def validate(self, attrs):
        # Usa a categoria do payload ou, se não veio, a actual da instância
        categoria = attrs.get('categoria', self.instance.categoria if self.instance else None)
        atributos_input = attrs.get('atributos')
        # Só valida atributos se foram enviados
        if atributos_input is not None:
            _validar_atributos_obrigatorios(categoria, atributos_input)
        return attrs

    def update(self, instance, validated_data):
        atributos = validated_data.pop('atributos', None)

        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save()

        if atributos is not None:
            instance.atributos.all().delete()

            # --- CORREÇÃO AQUI ---
            atribs = {
                a.id: a
                for a in AtributoCategoria.objects.filter(
                    id__in=[x['atributo_id'] for x in atributos],
                ).filter(
                    Q(categoria=instance.categoria) | Q(categoria=instance.categoria.pai)
                )
            }
            # --- FIM DA CORREÇÃO ---

            for item in atributos:
                atrib = atribs.get(item['atributo_id'])
                if atrib:
                    AtributoAnuncio.objects.create(
                        anuncio=instance, atributo=atrib, valor=item['valor'],
                    )

        return instance


class UploadImagensSerializer(serializers.Serializer):
    anuncio_id = serializers.IntegerField()
    imagens = serializers.ListField(
        child=serializers.ImageField(), max_length=10
    )

    def validate_anuncio_id(self, value):
        user = self.context['request'].user
        try:
            Anuncio.objects.get(pk=value, utilizador=user)
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