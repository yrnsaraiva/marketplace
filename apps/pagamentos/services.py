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
    import time
    ts = int(time.time()) % 100000  # 5 dígitos
    return f"PAG{pagamento_id:06d}{ts:05d}"


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
            self._criar_destaque_automatico(anuncio, subscricao)

        return anuncio

    def _criar_destaque_automatico(self, anuncio, subscricao):
        from apps.pagamentos.models import DestaqueAnuncio
        from datetime import timedelta

        DestaqueAnuncio.objects.create(
            anuncio=anuncio,
            subscricao=subscricao,
            fim_em=timezone.now() + timedelta(days=subscricao.plano.dias_destaque_incluidos),
            activo=True,
        )

    @transaction.atomic
    def iniciar_compra(self, plano_id):
        """
        Inicia a compra de um plano.

        PLANO GRATUITO (preco == 0):
          → Cancela subscrição gratuita anterior se existir.
          → Cria Subscrição com estado='activa' imediatamente.
          → Cria Pagamento com metodo='gratuito', estado='confirmado', valor=0.
          → NÃO chama a PaySuite (que rejeita amount=0).
          → Devolve o pagamento com checkout_url=None.

        PLANO PAGO (preco > 0):
          → Cria Subscrição (pendente) + Pagamento (pendente).
          → Chama PaySuite para obter checkout_url.
          → O utilizador é redirecionado para o checkout PaySuite.
        """
        from datetime import timedelta

        try:
            plano = PlanoPublicacao.objects.get(pk=plano_id, activo=True)
        except PlanoPublicacao.DoesNotExist:
            raise ValueError('Plano não encontrado ou inactivo.')

        # ── PLANO GRATUITO ────────────────────────────────────────────────────
        if plano.gratuito:
            logger.info("Plano gratuito — activar directamente sem PaySuite: %s", plano.nome)

            # Cancelar subscrição gratuita anterior para evitar duplicados
            SubscricaoUtilizador.objects.filter(
                utilizador=self.utilizador,
                plano__preco=0,
                estado='activa',
            ).update(estado='cancelada')

            subscricao = SubscricaoUtilizador.objects.create(
                utilizador=self.utilizador,
                plano=plano,
                estado='activa',
                creditos_totais=plano.max_anuncios,
                creditos_usados=0,
                preco_pago=0,
                inicio_em=timezone.now(),
                expira_em=timezone.now() + timedelta(days=plano.duracao_subscricao_dias),
            )

            pagamento = Pagamento.objects.create(
                subscricao=subscricao,
                metodo='gratuito',
                estado='confirmado',
                valor=0,
                confirmado_em=timezone.now(),
            )

            # Compatibilidade com IniciarCompraView (espera checkout_url)
            pagamento.checkout_url = None
            return pagamento

        # ── PLANO PAGO ────────────────────────────────────────────────────────
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
            metodo='manual',
            estado='pendente',
            valor=plano.preco,
        )

        referencia = _gerar_referencia(pagamento.pk)
        from django.conf import settings
        base_return  = getattr(settings, 'PAYSUITE_RETURN_URL', '').rstrip('/')
        return_url   = f"{base_return}/{pagamento.pk}/" if base_return else None
        callback_url = getattr(settings, 'PAYSUITE_CALLBACK_URL', '') or None

        try:
            client    = PaySuiteClient()
            resultado = client.criar_pagamento(
                amount=float(plano.preco),
                reference=referencia,
                description=f"Plano {plano.nome}",
                return_url=return_url,
                callback_url=callback_url,
            )
        except PaySuiteError as e:
            logger.error("PaySuite erro ao criar pagamento: %s", e)
            pagamento.resposta_gateway = {"erro": str(e)}
            pagamento.estado = 'falhado'
            pagamento.save(update_fields=['estado', 'resposta_gateway', 'actualizado_em'])
            raise

        pagamento.referencia_externa = resultado.get("id", "")
        pagamento.resposta_gateway   = resultado
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

        if resultado.get("status") in ("paid", "completed") or \
           resultado.get("transaction", {}).get("status") == "completed":
            pagamento.confirmar()

        return pagamento