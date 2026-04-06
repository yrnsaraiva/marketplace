from rest_framework import generics
from rest_framework.permissions import AllowAny
from .models import Categoria
from .serializers import CategoriaSerializer


class CategoriaListView(generics.ListAPIView):
    serializer_class = CategoriaSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Categoria.objects.filter(
            activa=True, pai__isnull=True
        ).prefetch_related('subcategorias', 'atributos')


class CategoriaDetalheView(generics.RetrieveAPIView):
    serializer_class = CategoriaSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return Categoria.objects.filter(
            activa=True
        ).prefetch_related('subcategorias', 'atributos')