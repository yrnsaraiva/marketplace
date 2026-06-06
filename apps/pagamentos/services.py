"""
apps/pagamentos/services.py

Lógica de negócio para pagamentos e publicação de anúncios.
Integra com a API PaySuite para M-Pesa, e-Mola e Cartão.
"""

import logging
import uuid

from django.db import transaction
from django.utils import timezone

from .models import SubscricaoUtilizador, PlanoPublicacao, Pagamento
from .paysuite import PaySuiteClient, PaySuiteError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gerar_referencia(pagamento_id: int) -> str:
    """Gera uma referência única para a PaySuite (máx. 50 chars)."""
    return f"PAG-{pagamento_id:08d}"


# ---------------------------------------------------------------------------
# PublicacaoService
# ---------------------------------------------------------------------------

class PublicacaoService:

    def __init__(self, utilizador):
        self.utilizador = utilizador

    # ------------------------------------------------------------------
    # Obter subscrição válida com crédito disponível
    # ------------------------------------------------------------------

    def subscricao_activa(self):
        """
        Devolve (subscricao, None) se o utilizador tem crédito disponível,
        ou (None, mensagem_de_erro) caso contrário.
        """
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

    # ------------------------------------------------------------------
    # Publicar anúncio (consome crédito)
    # ------------------------------------------------------------------

    @transaction.atomic
    def publicar(self, anuncio):
        """
        Consome 1 crédito da subscrição activa e activa o anúncio.
        Lança ValueError se não houver crédito disponível.
        """
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

    # ------------------------------------------------------------------
    # Iniciar compra via PaySuite
    # ------------------------------------------------------------------

    @transaction.atomic
    def iniciar_compra(self, plano_id, metodo_pagamento, telefone=''):
        """
        Cria Subscrição (pendente) + Pagamento (pendente) e inicia
        o fluxo PaySuite quando o método é 'mpesa', 'emola' ou 'credit_card'.

        Para o método 'manual' (confirmação por admin), não chama a PaySuite.

        Devolve o objecto Pagamento enriquecido com:
            - pagamento.checkout_url  — URL de redirect para o utilizador
              (None para pagamentos manuais)
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

        pagamento = Pagamento.objects.create(
            subscricao=subscricao,
            metodo=metodo_pagamento,
            estado='pendente',
            valor=plano.preco,
            telefone_pagamento=telefone,
        )

        # Pagamentos manuais não passam pela PaySuite
        if metodo_pagamento == 'manual':
            pagamento.checkout_url = None
            return pagamento

        # Chamar PaySuite para os restantes métodos
        metodo_paysuite = _METODO_MAP.get(metodo_pagamento, metodo_pagamento)
        referencia = _gerar_referencia(pagamento.pk)

        try:
            client = PaySuiteClient()
            resultado = client.criar_pagamento(
                amount=float(plano.preco),
                reference=referencia,
                description=f"Plano {plano.nome}",
                method=metodo_paysuite,
            )
        except PaySuiteError as e:
            logger.error("PaySuite erro ao criar pagamento: %s", e)
            # Guardar o erro no pagamento mas não lançar excepção ainda —
            # deixar a view decidir o que mostrar ao utilizador.
            pagamento.resposta_gateway = {"erro": str(e)}
            pagamento.estado = 'falhado'
            pagamento.save(update_fields=['estado', 'resposta_gateway', 'actualizado_em'])
            raise

        # Guardar ID e checkout URL da PaySuite
        paysuite_id = resultado.get("id", "")
        checkout_url = resultado.get("checkout_url", "")

        pagamento.referencia_externa = paysuite_id
        pagamento.resposta_gateway = resultado
        pagamento.save(update_fields=[
            'referencia_externa', 'resposta_gateway', 'actualizado_em'
        ])

        pagamento.checkout_url = checkout_url
        return pagamento

    # ------------------------------------------------------------------
    # Sincronizar estado com PaySuite (polling manual ou após redirect)
    # ------------------------------------------------------------------

    def sincronizar_pagamento(self, pagamento: Pagamento) -> Pagamento:
        """
        Consulta a PaySuite pelo ID guardado em referencia_externa
        e actualiza o estado local se o pagamento foi confirmado.

        Devolve o pagamento actualizado.
        """
        if not pagamento.referencia_externa:
            return pagamento  # sem ID PaySuite, nada a fazer

        if pagamento.estado != 'pendente':
            return pagamento  # já resolvido

        try:
            client = PaySuiteClient()
            resultado = client.obter_pagamento(pagamento.referencia_externa)
        except PaySuiteError as e:
            logger.warning("PaySuite: erro ao sincronizar pagamento #%s: %s", pagamento.pk, e)
            return pagamento

        paysuite_status = resultado.get("status", "")
        pagamento.resposta_gateway = resultado
        pagamento.save(update_fields=['resposta_gateway', 'actualizado_em'])

        if paysuite_status == "paid":
            pagamento.confirmar()

        return pagamento


# Mapeamento dos métodos internos para os aceites pela PaySuite
_METODO_MAP = {
    'mpesa': 'mpesa',
    'emola': 'emola',
    'transferencia': 'credit_card',  # ajuste conforme necessário
    'manual': None,
}
