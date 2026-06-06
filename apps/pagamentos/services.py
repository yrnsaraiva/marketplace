"""
apps/pagamentos/services.py
"""
import logging
from django.db import transaction
from django.utils import timezone

from .models import SubscricaoUtilizador, PlanoPublicacao, Pagamento
from .paysuite import PaySuiteClient, PaySuiteError

logger = logging.getLogger(__name__)


def _gerar_referencia(pagamento_id: int) -> str:
    return f"PAG-{pagamento_id:08d}"


class PublicacaoService:

    def __init__(self, utilizador):
        self.utilizador = utilizador

    def subscricao_activa(self):
        subscricoes = SubscricaoUtilizador.objects.filter(
            utilizador=self.utilizador,
            estado='activa',
            expira_em__gt=timezone.now(),
        ).select_related('plano').order_by('expira_em')

        for sub in subscricoes:
            if sub.tem_credito():
                return sub, None

        if subscricoes.exists():
            return None, (
                'O seu plano não tem créditos disponíveis. '
                'Renove ou adquira um novo plano para publicar mais anúncios.'
            )

        return None, (
            'Não tem nenhum plano activo. '
            'Adquira um plano para publicar o seu anúncio.'
        )

    @transaction.atomic
    def publicar(self, anuncio):
        subscricao, erro = self.subscricao_activa()
        if erro:
            raise ValueError(erro)

        duracao_dias = subscricao.consumir_credito()
        anuncio.subscricao = subscricao
        anuncio.activar(duracao_dias=duracao_dias)

        if subscricao.plano.dias_destaque_incluidos > 0:
            self._criar_destaque_automatico(anuncio, subscricao.plano)

        return anuncio

    def _criar_destaque_automatico(self, anuncio, plano):
        from apps.pagamentos.models import DestaqueAnuncio
        from datetime import timedelta

        DestaqueAnuncio.objects.create(
            anuncio=anuncio,
            plano_destaque=None,
            origem='plano_publicacao',
            fim_em=timezone.now() + timedelta(days=plano.dias_destaque_incluidos),
            activo=True,
        )

    @transaction.atomic
    def iniciar_compra(self, plano_id):
        """
        Cria Subscrição + Pagamento pendentes e obtém o checkout_url da PaySuite.
        O utilizador é redirecionado para esse URL onde escolhe M-Pesa/e-Mola/Cartão.
        """
        plano = PlanoPublicacao.objects.get(pk=plano_id, activo=True)

        subscricao = SubscricaoUtilizador.objects.create(
            utilizador=self.utilizador,
            plano=plano,
            estado='pendente',
            creditos_totais=plano.max_anuncios,
            creditos_usados=0,
            preco_pago=plano.preco,
        )

        # Criar registo de pagamento sem método definido ainda (escolhido no checkout)
        pagamento = Pagamento.objects.create(
            subscricao=subscricao,
            metodo='manual',  # actualizado pelo webhook após pagamento
            estado='pendente',
            valor=plano.preco,
        )

        # Chamar PaySuite para obter o checkout_url
        referencia = _gerar_referencia(pagamento.pk)
        try:
            client = PaySuiteClient()
            resultado = client.criar_pagamento(
                amount=float(plano.preco),
                reference=referencia,
                description=f"Plano {plano.nome}",
            )
        except PaySuiteError as e:
            logger.error("PaySuite erro ao criar pagamento: %s", e)
            pagamento.resposta_gateway = {"erro": str(e)}
            pagamento.estado = 'falhado'
            pagamento.save(update_fields=['estado', 'resposta_gateway', 'actualizado_em'])
            raise

        pagamento.referencia_externa = resultado.get("id", "")
        pagamento.resposta_gateway = resultado
        pagamento.save(update_fields=['referencia_externa', 'resposta_gateway', 'actualizado_em'])

        pagamento.checkout_url = resultado.get("checkout_url", "")
        return pagamento

    def sincronizar_pagamento(self, pagamento: Pagamento) -> Pagamento:
        if not pagamento.referencia_externa or pagamento.estado != 'pendente':
            return pagamento

        try:
            client = PaySuiteClient()
            resultado = client.obter_pagamento(pagamento.referencia_externa)
        except PaySuiteError as e:
            logger.warning("PaySuite: erro ao sincronizar #%s: %s", pagamento.pk, e)
            return pagamento

        pagamento.resposta_gateway = resultado
        pagamento.save(update_fields=['resposta_gateway', 'actualizado_em'])

        if resultado.get("status") == "paid":
            pagamento.confirmar()

        return pagamento