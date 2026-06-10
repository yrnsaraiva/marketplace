from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('pesquisa/', views.pesquisa_view, name='anuncio-pesquisa'),
    path('anuncios/<int:pk>/', views.anuncio_detalhe_view, name='anuncio-detalhe-view'),
    path('anuncios/publicar/', views.anuncio_publicar_view, name='anuncio-publicar'),
    path('anuncios/<int:pk>/editar/', views.anuncio_editar_view, name='anuncio-editar-view'),
    path('planos/', views.planos_page_view, name='planos'),

    # Dashboard e área do utilizador
    path('dashboard/', views.dashboard_view, name='dashboard'),           # ← novo
    path('dashboard/anuncios/', views.meus_anuncios_view, name='meus-anuncios'),
    path('dashboard/favoritos/', views.favoritos_view, name='favoritos'), # ← novo
    path('dashboard/perfil/', views.perfil_view, name='perfil'),          # ← novo
    path('termos-e-condicoes/', views.termos_condicoes, name='termos-e-condicoes'),
    path('politica-de-privacidade', views.politica_view, name='politica-de-privacidade'),
    path('linha-do-cliente/', views.contactos, name='contactos'),
    path('como-funciona/', views.instrucoes, name='instrucoes'),
]