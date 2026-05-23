"""
services.py — Lógica de negócio para publicação de anúncios.

Uso típico na view de criação de anúncio:

    from apps.pagamentos.services import PublicacaoService

    service = PublicacaoService(utilizador=request.user)

    # 1. Verificar se pode publicar (e obter a subscrição activa)
    subscricao, erro = service.subscricao_activa()
    if erro:
        return Response({'erro': erro}, status=400)

    # 2. Publicar o anúncio consumindo 1 crédito
    anuncio = service.publicar(anuncio)
"""

from django.db import transaction
from django.utils import timezone

from .models import SubscricaoUtilizador, PlanoPublicacao, Pagamento


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

        Prioridade: subscrições mais antigas primeiro (FIFO),
        para não desperdiçar créditos mais antigos.
        """
        subscricoes = SubscricaoUtilizador.objects.filter(
            utilizador=self.utilizador,
            estado='activa',
            expira_em__gt=timezone.now(),
        ).select_related('plano').order_by('expira_em')

        for sub in subscricoes:
            if sub.tem_credito():
                return sub, None

        # Verificar se tem subscrição mas sem créditos
        tem_subscricao_activa = subscricoes.exists()
        if tem_subscricao_activa:
            return None, (
                'O seu plano não tem créditos disponíveis. '
                'Renove ou adquira um novo plano para publicar mais anúncios.'
            )

        return None, (
            'Não tem nenhum plano activo. '
            'Adquira um plano para publicar o seu anúncio.'
        )

    # ------------------------------------------------------------------
    # Publicar anúncio
    # ------------------------------------------------------------------

    @transaction.atomic
    def publicar(self, anuncio):
        """
        Consome 1 crédito da subscrição activa e activa o anúncio.

        Parâmetros:
            anuncio: instância de Anuncio (já guardada, estado='pendente_pagamento')

        Devolve o anúncio actualizado.

        Lança ValueError se não houver crédito disponível.
        """
        subscricao, erro = self.subscricao_activa()
        if erro:
            raise ValueError(erro)

        # Consumir crédito e obter duração definida pelo plano
        duracao_dias = subscricao.consumir_credito()

        # Ligar a subscrição ao anúncio e activá-lo
        anuncio.subscricao = subscricao
        anuncio.activar(duracao_dias=duracao_dias)

        # Se o plano incluir dias de destaque, criar automaticamente
        if subscricao.plano.dias_destaque_incluidos > 0:
            self._criar_destaque_automatico(anuncio, subscricao.plano)

        return anuncio

    # ------------------------------------------------------------------
    # Criar destaque automático (planos Premium/Turbo)
    # ------------------------------------------------------------------

    def _criar_destaque_automatico(self, anuncio, plano):
        """
        Cria um DestaqueAnuncio com origem 'plano_publicacao'
        para os planos que incluem dias de destaque.
        """
        from apps.pagamentos.models import DestaqueAnuncio
        from django.utils import timezone
        from datetime import timedelta

        DestaqueAnuncio.objects.create(
            anuncio=anuncio,
            plano_destaque=None,
            origem='plano_publicacao',
            fim_em=timezone.now() + timedelta(days=plano.dias_destaque_incluidos),
            activo=True,
        )

    # ------------------------------------------------------------------
    # Iniciar compra de plano
    # ------------------------------------------------------------------

    @transaction.atomic
    def iniciar_compra(self, plano_id, metodo_pagamento, telefone=''):
        """
        Cria uma Subscrição no estado 'pendente' e um Pagamento associado.
        Devolve o objecto Pagamento criado.

        O admin (ou callback do gateway) chama pagamento.confirmar()
        para activar tudo.
        """
        plano = PlanoPublicacao.objects.get(pk=plano_id, activo=True)

        subscricao = SubscricaoUtilizador.objects.create(
            utilizador=self.utilizador,
            plano=plano,
            estado='pendente',
            creditos_totais=plano.max_anuncios,  # None = ilimitado
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

        return pagamento