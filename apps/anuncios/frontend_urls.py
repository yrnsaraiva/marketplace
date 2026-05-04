from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('pesquisa/', views.pesquisa_view, name='anuncio-pesquisa'),
    path('anuncios/<int:pk>/', views.anuncio_detalhe_view, name='anuncio-detalhe-view'),
    path('anuncios/publicar/', views.anuncio_publicar_view, name='anuncio-publicar'),
    path('anuncios/<int:pk>/editar/', views.anuncio_editar_view, name='anuncio-editar-view'),
    path('anuncios/meus/', views.meus_anuncios_view, name='meus-anuncios'),
]