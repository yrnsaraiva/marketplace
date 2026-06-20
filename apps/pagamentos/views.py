"""
apps/pagamentos/views.py
"""
import json
import logging

from django.db import transaction
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


class PlanoListView(generics.ListAPIView):
    serializer_class = PlanoPublicacaoSerializer
    permission_classes = []

    def get_queryset(self):
        return PlanoPublicacao.objects.filter(activo=True).order_by('ordem', 'preco')


class IniciarCompraView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = IniciarCompraSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PublicacaoService(utilizador=request.user)
        try:
            pagamento = service.iniciar_compra(plano_id=serializer.validated_data['plano_id'])
        except PlanoPublicacao.DoesNotExist:
            return Response({'erro': 'Plano não encontrado ou inactivo.'}, status=status.HTTP_404_NOT_FOUND)
        except PaySuiteError as e:
            return Response({'erro': f'Erro ao iniciar pagamento: {e}'}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.exception('Erro ao iniciar compra')
            return Response({'erro': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = PagamentoSerializer(pagamento).data
        checkout_url = getattr(pagamento, 'checkout_url', None)
        if checkout_url:
            data['checkout_url'] = checkout_url
            data['gratuito'] = False
        else:
            data['checkout_url'] = None
            data['gratuito'] = (pagamento.metodo == 'gratuito')

        return Response(data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class PaySuiteWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        logger.info("PaySuite webhook recebido — body: %s", request.body[:500])

        from django.conf import settings
        webhook_secret = getattr(settings, 'PAYSUITE_WEBHOOK_SECRET', '')
        if webhook_secret:
            signature = request.headers.get('X-Webhook-Signature', '')
            try:
                client = PaySuiteClient()
                if not client.verificar_webhook(request.body, signature):
                    logger.warning("PaySuite webhook: assinatura inválida")
                    return Response({'erro': 'Assinatura inválida'}, status=status.HTTP_401_UNAUTHORIZED)
            except PaySuiteError as e:
                return Response({'erro': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({'erro': 'JSON inválido'}, status=status.HTTP_400_BAD_REQUEST)

        event       = payload.get('event')
        data        = payload.get('data', {})
        paysuite_id = data.get('id', '')

        # FIX: transição de estado atómica para evitar race condition
        # se PaySuite enviar o webhook duas vezes em simultâneo.
        # Usar update() com filtro de estado garante que só um request confirma.
        if event in ('payment.success', 'payment.completed') or \
           data.get('transaction', {}).get('status') == 'completed':

            with transaction.atomic():
                # Tenta transitar de 'pendente' → 'confirmado' atomicamente
                updated = Pagamento.objects.filter(
                    referencia_externa=paysuite_id,
                    estado='pendente',
                ).update(resposta_gateway=payload)

                if updated == 0:
                    # Já processado ou não encontrado
                    logger.info("PaySuite webhook: %s já processado ou não encontrado", paysuite_id)
                    return Response({'mensagem': 'Ignorado'})

                pagamento = Pagamento.objects.select_related('subscricao').get(
                    referencia_externa=paysuite_id
                )
                pagamento.confirmar()
                logger.info("Pagamento #%s confirmado via webhook", pagamento.pk)

        elif event == 'payment.failed':
            Pagamento.objects.filter(
                referencia_externa=paysuite_id, estado='pendente'
            ).update(estado='falhado', resposta_gateway=payload)
            logger.info("PaySuite webhook: pagamento %s falhado", paysuite_id)

        else:
            logger.info("PaySuite webhook: evento '%s' ignorado", event)

        return Response({'mensagem': 'OK'})


class PaySuiteRetornoView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request, pk):
        pagamento = get_object_or_404(Pagamento, pk=pk)
        if pagamento.estado != 'confirmado':
            service = PublicacaoService(utilizador=pagamento.subscricao.utilizador)
            pagamento = service.sincronizar_pagamento(pagamento)

        if pagamento.estado == 'confirmado':
            return redirect('/dashboard/?pagamento=sucesso')
        return redirect('/planos/?pagamento=pendente')


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