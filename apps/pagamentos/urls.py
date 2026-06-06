from django.urls import path
from . import views

urlpatterns = [
    # Planos disponíveis (público)
    path('planos/', views.PlanoListView.as_view(), name='plano-list'),

    # Iniciar compra — devolve checkout_url da PaySuite
    path('comprar/', views.IniciarCompraView.as_view(), name='iniciar-compra'),

    # Webhook da PaySuite (configurar este URL no dashboard PaySuite)
    path('webhook/paysuite/', views.PaySuiteWebhookView.as_view(), name='paysuite-webhook'),

    # Redirect de retorno após checkout PaySuite
    path('retorno/<int:pk>/', views.PaySuiteRetornoView.as_view(), name='paysuite-retorno'),

    # Confirmação manual por admin/moderador
    path('confirmar/<int:pk>/', views.ConfirmarPagamentoView.as_view(), name='confirmar-pagamento'),

    # Histórico do utilizador
    path('subscricoes/', views.MinhasSubscricoesView.as_view(), name='minhas-subscricoes'),
    path('historico/', views.MeusPagamentosView.as_view(), name='meus-pagamentos'),
]

