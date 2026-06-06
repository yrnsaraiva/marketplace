"""
apps/pagamentos/views.py

Endpoints para:
  - Listar planos de publicação disponíveis
  - Iniciar compra de plano (cria Subscrição + Pagamento pendente)
  - Listar histórico de pagamentos do utilizador
  - Listar subscrições do utilizador
  - Confirmar pagamento manualmente (apenas admin/moderador)
"""
import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Pagamento, PlanoPublicacao, SubscricaoUtilizador
from .services import PublicacaoService
from .serializers import (
    PlanoPublicacaoSerializer,
    SubscricaoSerializer,
    PagamentoSerializer,
    IniciarCompraSerializer,
)

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
# Compra de plano
# ---------------------------------------------------------------------------
class IniciarCompraView(APIView):
    """
    Inicia a compra de um plano.
    Cria Subscrição (estado=pendente) + Pagamento (estado=pendente).
    O admin confirma manualmente via Django Admin ou via ConfirmarPagamentoView.
    """
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
        except Exception as e:
            logger.exception('Erro ao iniciar compra')
            return Response(
                {'erro': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            PagamentoSerializer(pagamento).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Confirmação manual (admin/moderador)
# ---------------------------------------------------------------------------
class ConfirmarPagamentoView(APIView):
    """
    Confirma um pagamento pendente e activa a subscrição associada.
    Apenas para staff/admin — em produção usar o callback do gateway.
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
        return Response(
            {'mensagem': 'Pagamento confirmado e subscrição activada.'},
        )


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