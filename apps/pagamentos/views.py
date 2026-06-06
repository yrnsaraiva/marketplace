"""
apps/pagamentos/views.py

Endpoints para:
  - Listar planos de publicação disponíveis
  - Iniciar compra (cria Subscrição + Pagamento, devolve checkout_url PaySuite)
  - Callback/webhook da PaySuite (confirmação automática)
  - Redirect de retorno após pagamento no checkout PaySuite
  - Listar histórico de pagamentos e subscrições do utilizador
  - Confirmar pagamento manualmente (admin/moderador)
"""
import json
import logging

from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pagamento, PlanoPublicacao, SubscricaoUtilizador
from .paysuite import PaySuiteClient, PaySuiteError
from .serializers import (
    IniciarCompraSerializer,
    PagamentoSerializer,
    PlanoPublicacaoSerializer,
    SubscricaoSerializer,
)
from .services import PublicacaoService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Planos disponíveis (público)
# ---------------------------------------------------------------------------

class PlanoListView(generics.ListAPIView):
    """Lista os planos de publicação activos ordenados por preço."""
    serializer_class = PlanoPublicacaoSerializer
    permission_classes = []  # público

    def get_queryset(self):
        return PlanoPublicacao.objects.filter(activo=True).order_by('ordem', 'preco')


# ---------------------------------------------------------------------------
# Compra de plano — inicia fluxo PaySuite
# ---------------------------------------------------------------------------

class IniciarCompraView(APIView):
    """
    Inicia a compra de um plano.

    Para métodos 'mpesa', 'emola' ou 'credit_card':
      - Cria Subscrição + Pagamento em estado 'pendente'
      - Chama a API PaySuite e devolve o checkout_url
      - O utilizador é redirecionado para o checkout PaySuite
      - Após pagamento, a PaySuite chama o webhook (PaySuiteWebhookView)

    Para método 'manual':
      - Apenas cria os registos; admin confirma no Django Admin
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = IniciarCompraSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PublicacaoService(utilizador=request.user)
        try:
            pagamento = service.iniciar_compra(
                plano_id=serializer.validated_data['plano_id'],
                metodo_pagamento=serializer.validated_data['metodo'],
                telefone=serializer.validated_data.get('telefone', ''),
            )
        except PlanoPublicacao.DoesNotExist:
            return Response(
                {'erro': 'Plano não encontrado ou inactivo.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PaySuiteError as e:
            return Response(
                {'erro': f'Erro ao iniciar pagamento: {e}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            logger.exception('Erro ao iniciar compra')
            return Response(
                {'erro': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = PagamentoSerializer(pagamento).data
        # Incluir o checkout_url no response para o frontend redirigir
        data['checkout_url'] = getattr(pagamento, 'checkout_url', None)
        return Response(data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Webhook PaySuite — recebe notificações automáticas
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class PaySuiteWebhookView(APIView):
    """
    Endpoint chamado pela PaySuite após confirmação de pagamento.

    URL a configurar no dashboard PaySuite:
        https://seudominio.com/api/pagamentos/webhook/paysuite/

    Eventos tratados:
        payment.success → confirma o Pagamento e activa a Subscrição
        payment.failed  → marca o Pagamento como falhado
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        # 1. Verificar assinatura
        signature = request.headers.get('X-Webhook-Signature', '')
        try:
            client = PaySuiteClient()
            if not client.verificar_webhook(request.body, signature):
                logger.warning("PaySuite webhook: assinatura inválida")
                return Response(
                    {'erro': 'Assinatura inválida'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except PaySuiteError as e:
            logger.error("PaySuite webhook: erro de configuração: %s", e)
            return Response({'erro': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 2. Parse do payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({'erro': 'JSON inválido'}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        data = payload.get('data', {})
        paysuite_id = data.get('id', '')
        request_id = payload.get('request_id', '')

        logger.info("PaySuite webhook: event=%s id=%s", event, paysuite_id)

        # 3. Encontrar pagamento pelo ID externo (referencia_externa)
        try:
            pagamento = Pagamento.objects.select_related(
                'subscricao'
            ).get(referencia_externa=paysuite_id)
        except Pagamento.DoesNotExist:
            logger.warning(
                "PaySuite webhook: pagamento não encontrado para id=%s", paysuite_id
            )
            # Responder 200 para a PaySuite não reenviar o webhook
            return Response({'mensagem': 'Pagamento não encontrado — ignorado'})

        # 4. Idempotência — ignorar se já processado
        if pagamento.estado != 'pendente':
            return Response({'mensagem': 'Já processado'})

        # 5. Processar evento
        pagamento.resposta_gateway = payload
        pagamento.save(update_fields=['resposta_gateway', 'actualizado_em'])

        if event == 'payment.success':
            pagamento.confirmar()
            logger.info(
                "PaySuite webhook: pagamento #%s confirmado (subscricao #%s activada)",
                pagamento.pk, pagamento.subscricao_id,
            )

        elif event == 'payment.failed':
            pagamento.estado = 'falhado'
            pagamento.save(update_fields=['estado', 'actualizado_em'])
            logger.info("PaySuite webhook: pagamento #%s falhado", pagamento.pk)

        else:
            logger.info("PaySuite webhook: evento desconhecido '%s' ignorado", event)

        return Response({'mensagem': 'OK'})


# ---------------------------------------------------------------------------
# Redirect de retorno após checkout PaySuite
# ---------------------------------------------------------------------------

class PaySuiteRetornoView(APIView):
    """
    O utilizador é redirecionado aqui após completar (ou abandonar)
    o checkout na PaySuite (parâmetro return_url).

    Sincroniza o estado do pagamento por polling e redirige para
    a página adequada.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        pagamento = get_object_or_404(
            Pagamento, pk=pk, subscricao__utilizador=request.user
        )
        service = PublicacaoService(utilizador=request.user)
        pagamento = service.sincronizar_pagamento(pagamento)

        if pagamento.estado == 'confirmado':
            return redirect('/conta/dashboard/?pagamento=sucesso')
        else:
            return redirect(f'/pagamentos/planos/?pagamento=pendente&ref={pk}')


# ---------------------------------------------------------------------------
# Confirmação manual (admin/moderador)
# ---------------------------------------------------------------------------

class ConfirmarPagamentoView(APIView):
    """
    Confirma um pagamento pendente manualmente.
    Apenas para staff/admin — em produção usar o webhook da PaySuite.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (request.user.is_staff or request.user.papel in ('admin', 'moderador')):
            return Response(
                {'erro': 'Sem permissão para confirmar pagamentos.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        pagamento = get_object_or_404(Pagamento, pk=pk)

        if pagamento.estado != 'pendente':
            return Response(
                {'erro': f'Pagamento já está no estado "{pagamento.estado}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pagamento.confirmar(confirmado_por=request.user)
        return Response({'mensagem': 'Pagamento confirmado e subscrição activada.'})


# ---------------------------------------------------------------------------
# Sincronizar estado de pagamento (polling do frontend)
# ---------------------------------------------------------------------------

class SincronizarPagamentoView(APIView):
    """
    Consulta a PaySuite e actualiza o estado de um pagamento pendente.
    Útil para o frontend verificar o estado sem esperar pelo webhook.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        pagamento = get_object_or_404(
            Pagamento, pk=pk, subscricao__utilizador=request.user
        )
        service = PublicacaoService(utilizador=request.user)
        pagamento = service.sincronizar_pagamento(pagamento)
        return Response(PagamentoSerializer(pagamento).data)


# ---------------------------------------------------------------------------
# Histórico do utilizador
# ---------------------------------------------------------------------------

class MinhasSubscricoesView(generics.ListAPIView):
    """Lista as subscrições do utilizador autenticado."""
    serializer_class = SubscricaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            SubscricaoUtilizador.objects
            .filter(utilizador=self.request.user)
            .select_related('plano')
            .order_by('-criado_em')
        )


class MeusPagamentosView(generics.ListAPIView):
    """Lista os pagamentos do utilizador autenticado."""
    serializer_class = PagamentoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Pagamento.objects
            .filter(subscricao__utilizador=self.request.user)
            .select_related('subscricao__plano')
            .order_by('-criado_em')
        )
