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


class IniciarCompraSerializer(serializers.Serializer):
    """
    O método de pagamento é tratado pelo checkout da PaySuite —
    só precisamos do plano_id.
    """
    plano_id = serializers.IntegerField()