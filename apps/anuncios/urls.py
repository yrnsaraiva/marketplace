from django.urls import path
from . import views

urlpatterns = [
    path('', views.AnuncioListView.as_view(), name='anuncio-list'),
    path('criar/', views.AnuncioCriarView.as_view(), name='anuncio-criar'),
    path('upload-imagens/', views.UploadImagensView.as_view(), name='upload-imagens'),
    path('meus/', views.MeusAnunciosView.as_view(), name='meus-anuncios'),
    path('favoritos/', views.MeusFavoritosView.as_view(), name='favoritos'),
    path('<int:pk>/', views.AnuncioDetalheView.as_view(), name='anuncio-detalhe'),
    path('<int:pk>/editar/', views.AnuncioEditarView.as_view(), name='anuncio-editar'),
    path('<int:pk>/favorito/', views.FavoritoToggleView.as_view(), name='favorito-toggle'),
    path('<int:pk>/registar-contacto/', views.RegistarContactoView.as_view(), name='registar-contacto'),
    path('<int:pk>/eliminar/', views.EliminarAnuncioView.as_view(), name='anuncio-eliminar'),
]