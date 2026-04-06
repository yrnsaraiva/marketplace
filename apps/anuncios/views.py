from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from .models import Anuncio, ImagemAnuncio, Favorito
from .serializers import (
    AnuncioListSerializer, AnuncioDetalheSerializer,
    AnuncioCriarSerializer, UploadImagensSerializer, FavoritoSerializer
)
from .filters import AnuncioFilter


class AnuncioListView(generics.ListAPIView):
    serializer_class = AnuncioListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AnuncioFilter
    search_fields = ['titulo', 'descricao', 'cidade']
    ordering_fields = ['publicado_em', 'preco', 'visualizacoes']
    ordering = ['-publicado_em']

    def get_queryset(self):
        return Anuncio.objects.filter(
            estado='activo'
        ).select_related('categoria', 'utilizador').prefetch_related('imagens')


class AnuncioDetalheView(generics.RetrieveAPIView):
    serializer_class = AnuncioDetalheSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Anuncio.objects.filter(
            estado='activo'
        ).select_related('categoria', 'utilizador').prefetch_related('imagens', 'atributos')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.registar_visualizacao()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class AnuncioCriarView(generics.CreateAPIView):
    serializer_class = AnuncioCriarSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        anuncio = serializer.save()
        user.total_anuncios += 1
        user.save(update_fields=['total_anuncios'])
        return anuncio


class AnuncioEditarView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AnuncioCriarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Anuncio.objects.filter(utilizador=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.estado = 'eliminado'
        instance.save(update_fields=['estado'])
        user = request.user
        user.total_anuncios = max(0, user.total_anuncios - 1)
        user.save(update_fields=['total_anuncios'])
        return Response(
            {'mensagem': 'Anúncio eliminado com sucesso.'},
            status=status.HTTP_200_OK
        )


class UploadImagensView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        anuncio_id = request.data.get('anuncio_id')
        imagens = request.FILES.getlist('imagens')

        anuncio = get_object_or_404(
            Anuncio, pk=anuncio_id, utilizador=request.user
        )

        if anuncio.imagens.count() + len(imagens) > 10:
            return Response(
                {'erro': 'Máximo de 10 imagens por anúncio.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        urls = []
        for i, imagem in enumerate(imagens):
            is_principal = (anuncio.imagens.count() == 0 and i == 0)
            img = ImagemAnuncio.objects.create(
                anuncio=anuncio,
                imagem=imagem,
                ordem=anuncio.imagens.count() + i,
                principal=is_principal
            )
            urls.append(request.build_absolute_uri(img.imagem.url))

        return Response({'urls': urls, 'total': anuncio.imagens.count()})


class MeusAnunciosView(generics.ListAPIView):
    serializer_class = AnuncioListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Anuncio.objects.filter(
            utilizador=self.request.user
        ).exclude(estado='eliminado').prefetch_related('imagens')


class FavoritoToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        anuncio = get_object_or_404(Anuncio, pk=pk, estado='activo')
        favorito, criado = Favorito.objects.get_or_create(
            utilizador=request.user, anuncio=anuncio
        )
        if not criado:
            favorito.delete()
            return Response({'mensagem': 'Removido dos favoritos.', 'favorito': False})
        return Response({'mensagem': 'Adicionado aos favoritos.', 'favorito': True})


class MeusFavoritosView(generics.ListAPIView):
    serializer_class = FavoritoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorito.objects.filter(
            utilizador=self.request.user
        ).select_related('anuncio').prefetch_related('anuncio__imagens')