from rest_framework import serializers
from .models import PlanoPublicacao, SubscricaoUtilizador, Pagamento


class PlanoPublicacaoSerializer(serializers.ModelSerializer):
    ilimitado = serializers.BooleanField(read_only=True)
    preco_por_anuncio = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = PlanoPublicacao
        fields = [
            'id', 'nome', 'descricao', 'tipo', 'preco',
            'max_anuncios', 'duracao_anuncio_dias',
            'duracao_subscricao_dias', 'max_imagens',
            'dias_destaque_incluidos', 'ordem',
            'ilimitado', 'preco_por_anuncio',
        ]


class SubscricaoSerializer(serializers.ModelSerializer):
    plano_nome = serializers.CharField(source='plano.nome', read_only=True)
    creditos_disponiveis = serializers.IntegerField(read_only=True)
    valida = serializers.BooleanField(read_only=True)

    class Meta:
        model = SubscricaoUtilizador
        fields = [
            'id', 'plano_nome', 'estado',
            'creditos_totais', 'creditos_usados', 'creditos_disponiveis',
            'inicio_em', 'expira_em', 'preco_pago', 'valida',
            'criado_em',
        ]
        read_only_fields = fields


class PagamentoSerializer(serializers.ModelSerializer):
    plano_nome = serializers.CharField(
        source='subscricao.plano.nome', read_only=True
    )
    subscricao_id = serializers.IntegerField(
        source='subscricao.id', read_only=True
    )

    class Meta:
        model = Pagamento
        fields = [
            'id', 'subscricao_id', 'plano_nome',
            'metodo', 'estado', 'valor',
            'referencia_externa', 'telefone_pagamento',
            'confirmado_em', 'criado_em',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Compra manual (legado)
# ---------------------------------------------------------------------------
class IniciarCompraSerializer(serializers.Serializer):
    METODO_CHOICES = ['mpesa', 'emola', 'transferencia', 'manual']

    plano_id = serializers.IntegerField()
    metodo = serializers.ChoiceField(choices=METODO_CHOICES)
    telefone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_metodo(self, value):
        if value in ('mpesa', 'emola') and not self.initial_data.get('telefone'):
            raise serializers.ValidationError(
                'Número de telefone é obrigatório para pagamentos M-Pesa/e-Mola.'
            )
        return value


# ---------------------------------------------------------------------------
# Compra via PaySuite (checkout online)
# ---------------------------------------------------------------------------
class IniciarCompraPaysuiteSerializer(serializers.Serializer):
    """
    Payload para iniciar o checkout no PaySuite.

    Campos:
        plano_id  — ID do PlanoPublicacao
        metodo    — (opcional) 'mpesa', 'emola' ou 'credit_card'
                     Se omitido, o utilizador escolhe no checkout do PaySuite.
    """
    METODO_CHOICES = ['mpesa', 'emola', 'credit_card']

    plano_id = serializers.IntegerField()
    metodo = serializers.ChoiceField(
        choices=METODO_CHOICES,
        required=False,
        allow_null=True,
        default=None,
    )