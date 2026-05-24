from django.urls import path
from . import views

urlpatterns = [
    path('planos/', views.PlanoListView.as_view(), name='plano-list'),
    path('comprar/', views.IniciarCompraView.as_view(), name='iniciar-compra'),
    path('confirmar/<int:pk>/', views.ConfirmarPagamentoView.as_view(), name='confirmar-pagamento'),
    path('subscricoes/', views.MinhasSubscricoesView.as_view(), name='minhas-subscricoes'),
    path('historico/', views.MeusPagamentosView.as_view(), name='meus-pagamentos'),
]
