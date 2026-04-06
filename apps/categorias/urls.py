from django.urls import path
from . import views

urlpatterns = [
    path('', views.CategoriaListView.as_view(), name='categoria-list'),
    path('<slug:slug>/', views.CategoriaDetalheView.as_view(), name='categoria-detalhe'),
]