"""
apps/pagamentos/views.py
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
    serializer_class = PlanoPublicacaoSerializer
    permission_classes = []

    def get_queryset(self):
        return PlanoPublicacao.objects.filter(activo=True).order_by('ordem', 'preco')


# ---------------------------------------------------------------------------
# Iniciar compra — devolve checkout_url da PaySuite
# ---------------------------------------------------------------------------
class IniciarCompraView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = IniciarCompraSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PublicacaoService(utilizador=request.user)
        try:
            pagamento = service.iniciar_compra(
                plano_id=serializer.validated_data['plano_id'],
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
            return Response({'erro': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = PagamentoSerializer(pagamento).data
        data['checkout_url'] = getattr(pagamento, 'checkout_url', None)
        return Response(data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Webhook PaySuite
# ---------------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class PaySuiteWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get('X-Webhook-Signature', '')
        try:
            client = PaySuiteClient()
            if not client.verificar_webhook(request.body, signature):
                return Response({'erro': 'Assinatura inválida'}, status=status.HTTP_401_UNAUTHORIZED)
        except PaySuiteError as e:
            return Response({'erro': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({'erro': 'JSON inválido'}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        data = payload.get('data', {})
        paysuite_id = data.get('id', '')

        logger.info("PaySuite webhook: event=%s id=%s", event, paysuite_id)

        try:
            pagamento = Pagamento.objects.select_related('subscricao').get(
                referencia_externa=paysuite_id
            )
        except Pagamento.DoesNotExist:
            return Response({'mensagem': 'Ignorado'})

        if pagamento.estado != 'pendente':
            return Response({'mensagem': 'Já processado'})

        pagamento.resposta_gateway = payload
        pagamento.save(update_fields=['resposta_gateway', 'actualizado_em'])

        if event == 'payment.success':
            pagamento.confirmar()
            logger.info("Pagamento #%s confirmado — subscrição #%s activada",
                        pagamento.pk, pagamento.subscricao_id)
        elif event == 'payment.failed':
            pagamento.estado = 'falhado'
            pagamento.save(update_fields=['estado', 'actualizado_em'])

        return Response({'mensagem': 'OK'})


# ---------------------------------------------------------------------------
# Redirect de retorno após checkout PaySuite
# ---------------------------------------------------------------------------
class PaySuiteRetornoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        pagamento = get_object_or_404(
            Pagamento, pk=pk, subscricao__utilizador=request.user
        )
        service = PublicacaoService(utilizador=request.user)
        pagamento = service.sincronizar_pagamento(pagamento)

        if pagamento.estado == 'confirmado':
            return redirect('/conta/dashboard/?pagamento=sucesso')
        return redirect(f'/planos/?pagamento=pendente&ref={pk}')


# ---------------------------------------------------------------------------
# Confirmação manual (admin/moderador)
# ---------------------------------------------------------------------------
class ConfirmarPagamentoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not (request.user.is_staff or request.user.papel in ('admin', 'moderador')):
            return Response({'erro': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

        pagamento = get_object_or_404(Pagamento, pk=pk)
        if pagamento.estado != 'pendente':
            return Response(
                {'erro': f'Pagamento já está "{pagamento.estado}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pagamento.confirmar(confirmado_por=request.user)
        return Response({'mensagem': 'Pagamento confirmado e subscrição activada.'})


# ---------------------------------------------------------------------------
# Histórico do utilizador
# ---------------------------------------------------------------------------
class MinhasSubscricoesView(generics.ListAPIView):
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
    serializer_class = PagamentoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Pagamento.objects
            .filter(subscricao__utilizador=self.request.user)
            .select_related('subscricao__plano')
            .order_by('-criado_em')
        )