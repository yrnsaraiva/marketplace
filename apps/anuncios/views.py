from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required

from .models import Anuncio, ImagemAnuncio, Favorito
from .serializers import (
    AnuncioListSerializer, AnuncioDetalheSerializer,
    AnuncioCriarSerializer, UploadImagensSerializer, FavoritoSerializer
)
from .filters import AnuncioFilter


PROVINCIAS = [
    'Maputo', 'Gaza', 'Inhambane', 'Sofala',
    'Manica', 'Tete', 'Zambézia', 'Nampula',
    'Niassa', 'Cabo Delgado'
]


# ─────────────────────────────────────────────────────────────
# HELPER: serializar anúncio para dicionário (usado em múltiplas views)
# ─────────────────────────────────────────────────────────────

def _anuncio_para_dict(anuncio, request):
    item = {
        'id': anuncio.id,
        'titulo': anuncio.titulo,
        'preco': anuncio.preco,
        'estado': anuncio.estado,
        'get_estado_display': anuncio.get_estado_display(),
        'categoria_nome': anuncio.categoria.nome,
        'visualizacoes': anuncio.visualizacoes,
        'publicado_em': anuncio.publicado_em,
        'provincia': anuncio.provincia,
        'cidade': anuncio.cidade,
        'condicao': anuncio.condicao,
        'imagem_principal': None,
    }
    img = anuncio.imagens.filter(principal=True).first() or anuncio.imagens.first()
    if img:
        item['imagem_principal'] = request.build_absolute_uri(img.imagem.url)
    return item


# ─────────────────────────────────────────────────────────────
# API VIEWS
# ─────────────────────────────────────────────────────────────

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

        anuncio = get_object_or_404(Anuncio, pk=anuncio_id, utilizador=request.user)

        # Respeita o limite de imagens do plano em vez de hardcoded 10
        limite = anuncio.max_imagens_permitidas
        if anuncio.imagens.count() + len(imagens) > limite:
            return Response(
                {'erro': f'Máximo de {limite} imagens permitidas pelo seu plano.'},
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


# ─────────────────────────────────────────────────────────────
# FRONTEND VIEWS
# ─────────────────────────────────────────────────────────────

def home_view(request):
    from apps.pagamentos.models import DestaqueAnuncio
    from apps.categorias.models import Categoria

    categorias = Categoria.objects.filter(activa=True, pai__isnull=True)

    destacados_ids = DestaqueAnuncio.objects.filter(
        activo=True
    ).values_list('anuncio_id', flat=True)[:8]

    anuncios_destacados = [
        _anuncio_para_dict(a, request)
        for a in Anuncio.objects.filter(
            id__in=destacados_ids, estado='activo'
        ).select_related('categoria').prefetch_related('imagens')
    ]

    anuncios_recentes = [
        _anuncio_para_dict(a, request)
        for a in Anuncio.objects.filter(
            estado='activo'
        ).select_related('categoria').prefetch_related('imagens').order_by('-publicado_em')[:8]
    ]

    return render(request, 'anuncios/index.html', {
        'categorias': categorias,
        'anuncios_destacados': anuncios_destacados,
        'anuncios_recentes': anuncios_recentes,
    })


def pesquisa_view(request):
    from apps.categorias.models import Categoria

    queryset = Anuncio.objects.filter(
        estado='activo'
    ).select_related('categoria').prefetch_related('imagens')

    search = request.GET.get('search', '')
    categoria_slug = request.GET.get('categoria', '')
    provincia = request.GET.get('provincia', '')
    preco_min = request.GET.get('preco_min', '')
    preco_max = request.GET.get('preco_max', '')
    condicao = request.GET.get('condicao', '')
    ordering = request.GET.get('ordering', '-publicado_em')

    if search:
        queryset = queryset.filter(titulo__icontains=search) | queryset.filter(descricao__icontains=search)
    if categoria_slug:
        queryset = queryset.filter(categoria__slug=categoria_slug)
    if provincia:
        queryset = queryset.filter(provincia__iexact=provincia)
    if preco_min:
        queryset = queryset.filter(preco__gte=preco_min)
    if preco_max:
        queryset = queryset.filter(preco__lte=preco_max)
    if condicao:
        queryset = queryset.filter(condicao=condicao)

    ordering_validos = ['publicado_em', '-publicado_em', 'preco', '-preco', '-visualizacoes']
    if ordering in ordering_validos:
        queryset = queryset.order_by(ordering)

    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    page_obj.object_list = [_anuncio_para_dict(a, request) for a in page_obj]

    return render(request, 'anuncios/pesquisa.html', {
        'page_obj': page_obj,
        'categorias': Categoria.objects.filter(activa=True, pai__isnull=True),
        'categorias_selecionadas': request.GET.getlist('categoria'),
        'provincias': PROVINCIAS,
    })


def anuncio_detalhe_view(request, pk):
    anuncio = get_object_or_404(
        Anuncio.objects.select_related('categoria', 'utilizador')
                       .prefetch_related('imagens', 'atributos__atributo'),
        pk=pk, estado='activo'
    )
    anuncio.registar_visualizacao()

    relacionados = [
        _anuncio_para_dict(a, request)
        for a in Anuncio.objects.filter(
            categoria=anuncio.categoria, estado='activo'
        ).exclude(pk=pk).prefetch_related('imagens')[:4]
    ]

    return render(request, 'anuncios/detalhes.html', {
        'anuncio': anuncio,
        'anuncios_relacionados': relacionados,
    })


@login_required
def anuncio_publicar_view(request):
    from apps.categorias.models import Categoria
    from apps.pagamentos.models import PlanoDestaque

    return render(request, 'anuncios/publicar.html', {
        'categorias': Categoria.objects.filter(activa=True, pai__isnull=True),
        'planos': PlanoDestaque.objects.filter(activo=True),
    })


@login_required
def anuncio_editar_view(request, pk):
    from apps.categorias.models import Categoria

    anuncio = get_object_or_404(Anuncio, pk=pk, utilizador=request.user)
    return render(request, 'anuncios/publicar.html', {
        'anuncio': anuncio,
        'categorias': Categoria.objects.filter(activa=True, pai__isnull=True),
        'planos': [],
    })

# ─────────────────────────────────────────────────────────────
# HELPERS ÁREA DO UTILIZADOR
# ─────────────────────────────────────────────────────────────

def _get_subscricao_activa(user):
    from django.utils import timezone
    from apps.pagamentos.models import SubscricaoUtilizador
    return SubscricaoUtilizador.objects.filter(
        utilizador=user,
        estado='activa',
        expira_em__gt=timezone.now(),
    ).select_related('plano').order_by('expira_em').first()


def _sidebar_context(user):
    """Dados comuns a todas as páginas da área do utilizador."""
    from django.db.models import Sum

    total_anuncios = Anuncio.objects.filter(
        utilizador=user
    ).exclude(estado='eliminado').count()

    total_visualizacoes = Anuncio.objects.filter(
        utilizador=user
    ).exclude(estado='eliminado').aggregate(
        total=Sum('visualizacoes')
    )['total'] or 0

    total_favoritos = Favorito.objects.filter(utilizador=user).count()

    return {
        'total_anuncios': total_anuncios,
        'total_visualizacoes': total_visualizacoes,
        'total_favoritos': total_favoritos,
        'subscricao_activa': _get_subscricao_activa(user),
    }


def _favoritos_lista(user, request, limite=None):
    """Devolve lista de favoritos serializada para o template."""
    qs = Favorito.objects.filter(
        utilizador=user
    ).select_related('anuncio__categoria').prefetch_related('anuncio__imagens').order_by('-criado_em')

    if limite:
        qs = qs[:limite]

    resultado = []
    for fav in qs:
        img = fav.anuncio.imagens.filter(principal=True).first() or fav.anuncio.imagens.first()
        resultado.append({'anuncio': {
            'id': fav.anuncio.id,
            'titulo': fav.anuncio.titulo,
            'preco': fav.anuncio.preco,
            'cidade': fav.anuncio.cidade,
            'categoria_nome': fav.anuncio.categoria.nome,
            'imagem_principal': request.build_absolute_uri(img.imagem.url) if img else None,
        }})
    return resultado


# ─────────────────────────────────────────────────────────────
# VIEWS DA ÁREA DO UTILIZADOR
# ─────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    anuncios_qs = Anuncio.objects.filter(
        utilizador=request.user
    ).exclude(estado='eliminado').select_related('categoria').prefetch_related('imagens').order_by('-publicado_em')

    ctx = _sidebar_context(request.user)
    ctx.update({
        'meus_anuncios': [_anuncio_para_dict(a, request) for a in anuncios_qs[:5]],
        'favoritos': _favoritos_lista(request.user, request, limite=4),
        'active_tab': 'dashboard',
        'page_title': 'Meu Painel',
        'page_subtitle': 'Visão geral dos seus anúncios e actividade',
    })
    return render(request, 'users/dashboard.html', ctx)


@login_required
def meus_anuncios_view(request):
    estado_filtros = [
        ('Todos', ''),
        ('Activos', 'activo'),
        ('Pendente', 'pendente_pagamento'),
        ('Pausados', 'pausado'),
        ('Expirados', 'expirado'),
    ]
    estado_actual = request.GET.get('estado', '')

    anuncios_qs = Anuncio.objects.filter(
        utilizador=request.user
    ).exclude(estado='eliminado').select_related('categoria').prefetch_related('imagens').order_by('-publicado_em')

    if estado_actual:
        anuncios_qs = anuncios_qs.filter(estado=estado_actual)

    paginator = Paginator(anuncios_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    page_obj.object_list = [_anuncio_para_dict(a, request) for a in page_obj]

    ctx = _sidebar_context(request.user)
    ctx.update({
        'page_obj': page_obj,
        'estado_filtros': estado_filtros,
        'estado_actual': estado_actual,
        'active_tab': 'anuncios',
        'page_title': 'Meus Anúncios',
        'page_subtitle': 'Todos os seus anúncios publicados',
    })
    return render(request, 'users/meus_anuncios.html', ctx)


@login_required
def favoritos_view(request):
    ctx = _sidebar_context(request.user)
    ctx.update({
        'favoritos': _favoritos_lista(request.user, request),
        'active_tab': 'favoritos',
        'page_title': 'Favoritos',
        'page_subtitle': 'Anúncios que guardou para mais tarde',
    })
    return render(request, 'users/favoritos.html', ctx)


@login_required
def perfil_view(request):
    ctx = _sidebar_context(request.user)
    ctx.update({
        'user': request.user,
        'provincias': PROVINCIAS,
        'active_tab': 'perfil',
        'page_title': 'O meu Perfil',
        'page_subtitle': 'Gerencie as suas informações pessoais',
    })
    return render(request, 'users/perfil.html', ctx)