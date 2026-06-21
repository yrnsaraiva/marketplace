import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import ContaActivaPermission, conta_activa_required
from .filters import AnuncioFilter
from .models import Anuncio, Favorito, ImagemAnuncio
from apps.pagamentos.models import PlanoPublicacao, SubscricaoUtilizador
from .serializers import (
    AnuncioCriarSerializer,
    AnuncioEditarSerializer,
    AnuncioDetalheSerializer,
    AnuncioListSerializer,
    FavoritoSerializer,
)

logger = logging.getLogger(__name__)

PROVINCIAS = [
    'Maputo', 'Gaza', 'Inhambane', 'Sofala',
    'Manica', 'Tete', 'Zambézia', 'Nampula',
    'Niassa', 'Cabo Delgado'
]


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------
def _anuncio_para_dict(anuncio, request):
    """Serializa um anúncio para dicionário simples (usado nos templates)."""
    imgs = list(anuncio.imagens.all())
    img = next(
        (i for i in imgs if i.principal),
        imgs[0] if imgs else None
    )
    return {
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
        'imagem_principal': request.build_absolute_uri(img.imagem.url) if img else None,

        'destacado': anuncio.destacado,
    }


def _get_subscricao_activa(user):
    """Devolve a subscrição activa mais antiga (FIFO) ou None."""
    return (
        SubscricaoUtilizador.objects
        .filter(utilizador=user, estado='activa', expira_em__gt=timezone.now())
        .select_related('plano')
        .order_by('expira_em')
        .first()
    )


def _sidebar_context(user):
    """Dados comuns a todas as páginas da área do utilizador."""
    total_anuncios = (
        Anuncio.objects.filter(utilizador=user)
        .exclude(estado='eliminado')
        .count()
    )
    total_visualizacoes = (
        Anuncio.objects.filter(utilizador=user)
        .exclude(estado='eliminado')
        .aggregate(total=Sum('visualizacoes'))['total'] or 0
    )
    total_favoritos = Favorito.objects.filter(utilizador=user).count()
    return {
        'total_anuncios': total_anuncios,
        'total_visualizacoes': total_visualizacoes,
        'total_favoritos': total_favoritos,
        'subscricao_activa': _get_subscricao_activa(user),
    }


def _favoritos_lista(user, request, limite=None):
    """Devolve lista de favoritos serializada para o template."""
    qs = (
        Favorito.objects
        .filter(utilizador=user)
        .select_related('anuncio__categoria')
        .prefetch_related('anuncio__imagens')
        .order_by('-criado_em')
    )
    if limite:
        qs = qs[:limite]

    resultado = []
    for fav in qs:
        imgs = list(fav.anuncio.imagens.all())
        img = next((i for i in imgs if i.principal), imgs[0] if imgs else None)
        resultado.append({
            'anuncio': {
                'id': fav.anuncio.id,
                'titulo': fav.anuncio.titulo,
                'preco': fav.anuncio.preco,
                'cidade': fav.anuncio.cidade,
                'categoria_nome': fav.anuncio.categoria.nome,
                'imagem_principal': (
                    request.build_absolute_uri(img.imagem.url) if img else None
                ),
            }
        })
    return resultado


# ---------------------------------------------------------------------------
# API - Anúncios
# ---------------------------------------------------------------------------
class AnuncioListView(generics.ListAPIView):
    serializer_class = AnuncioListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AnuncioFilter
    search_fields = ['titulo', 'descricao', 'cidade']
    ordering_fields = ['publicado_em', 'preco', 'visualizacoes']
    ordering = ['-publicado_em']

    def get_queryset(self):
        return (
            Anuncio.objects
            .filter(estado='activo')
            .select_related('categoria', 'utilizador')
            .prefetch_related('imagens', 'destaques')
        )


class AnuncioDetalheView(generics.RetrieveAPIView):
    serializer_class = AnuncioDetalheSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Anuncio.objects
            .filter(estado='activo')
            .select_related('categoria', 'utilizador')
            .prefetch_related('imagens', 'atributos__atributo')
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.registar_visualizacao(utilizador=request.user)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)




class AnuncioCriarView(generics.CreateAPIView):
    """
    Cria um anúncio, valida subscrição activa, grava atributos
    e opcionalmente aplica destaque avulso - tudo num só endpoint.
    Requer conta com email verificado e idade >= 18 anos.
    """
    serializer_class = AnuncioCriarSerializer
    permission_classes = [IsAuthenticated, ContaActivaPermission]


class AnuncioEditarView(generics.RetrieveUpdateAPIView):

    serializer_class = AnuncioEditarSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Anuncio.objects.filter(
            utilizador=self.request.user
        ).exclude(estado='eliminado')


class EliminarAnuncioView(APIView):
    """
    FIX: delete num endpoint separado com IsAuthenticated.
    Antes estava no AnuncioDetalheView com permission_classes=[AllowAny].
    DELETE /api/v1/anuncios/<pk>/eliminar/
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        anuncio = get_object_or_404(Anuncio, pk=pk, utilizador=request.user)
        if anuncio.estado == 'eliminado':
            return Response({'erro': 'Anúncio já eliminado.'}, status=status.HTTP_400_BAD_REQUEST)
        anuncio.estado = 'eliminado'
        anuncio.save(update_fields=['estado', 'actualizado_em'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UploadImagensView(APIView):
    """
    Upload de imagens para um anúncio existente.
    Respeita o limite de imagens definido pelo plano de subscrição.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        anuncio_id = request.data.get('anuncio_id')
        imagens = request.FILES.getlist('imagens')

        logger.info(
            'UploadImagens: user=%s anuncio_id=%r n_imagens=%d',
            request.user.id, anuncio_id, len(imagens)
        )

        if not anuncio_id:
            return Response(
                {'erro': 'anuncio_id é obrigatório.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not imagens:
            return Response(
                {'erro': 'Nenhuma imagem recebida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            anuncio_id = int(anuncio_id)
        except (ValueError, TypeError):
            return Response(
                {'erro': 'anuncio_id inválido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        anuncio = get_object_or_404(Anuncio, pk=anuncio_id, utilizador=request.user)

        limite = anuncio.max_imagens_permitidas
        existentes = anuncio.imagens.count()

        logger.info(
            'UploadImagens: anuncio=%d limite=%d existentes=%d a_enviar=%d',
            anuncio_id, limite, existentes, len(imagens)
        )

        if existentes + len(imagens) > limite:
            return Response(
                {'erro': f'O seu plano permite no máximo {limite} imagens. '
                         f'Já tem {existentes} carregadas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        urls = []
        for i, imagem in enumerate(imagens):
            is_principal = (existentes == 0 and i == 0)
            img = ImagemAnuncio.objects.create(
                anuncio=anuncio,
                imagem=imagem,
                ordem=existentes + i,
                principal=is_principal,
            )
            urls.append(request.build_absolute_uri(img.imagem.url))

        logger.info('UploadImagens: %d imagens guardadas para anuncio=%d', len(urls), anuncio_id)
        return Response({'urls': urls, 'total': anuncio.imagens.count()})


class EliminarImagemView(APIView):
    """
    DELETE /api/v1/anuncios/imagens/<pk>/
    Remove uma imagem de um anúncio. Só o dono pode remover.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        imagem = get_object_or_404(
            ImagemAnuncio,
            pk=pk,
            anuncio__utilizador=request.user,
        )
        # Se era a principal, promover a próxima imagem
        era_principal = imagem.principal
        anuncio = imagem.anuncio
        imagem.delete()

        if era_principal:
            proxima = anuncio.imagens.order_by('ordem').first()
            if proxima:
                proxima.principal = True
                proxima.save(update_fields=['principal'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeusAnunciosView(generics.ListAPIView):
    serializer_class = AnuncioListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Anuncio.objects
            .filter(utilizador=self.request.user)
            .exclude(estado='eliminado')
            .prefetch_related('imagens', 'destaques')
        )


class FavoritoToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        anuncio = get_object_or_404(Anuncio, pk=pk)

        # FIX: verificar se já é favorito ANTES de tentar criar
        try:
            favorito = Favorito.objects.get(utilizador=request.user, anuncio=anuncio)
            favorito.delete()
            return Response({'mensagem': 'Removido dos favoritos.', 'favorito': False})
        except Favorito.DoesNotExist:
            pass

        # FIX: verificar estado ANTES de criar o favorito
        if anuncio.estado != 'activo':
            return Response(
                {'erro': 'Este anúncio já não está disponível.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Favorito.objects.create(utilizador=request.user, anuncio=anuncio)
        return Response({'mensagem': 'Adicionado aos favoritos.', 'favorito': True})


class MeusFavoritosView(generics.ListAPIView):
    serializer_class = FavoritoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorito.objects.filter(
            utilizador=self.request.user
        ).select_related('anuncio').prefetch_related('anuncio__imagens', 'anuncio__destaques')


class RegistarContactoView(APIView):
    permission_classes = []

    def post(self, request, pk):
        Anuncio.objects.filter(pk=pk, estado='activo').update(
            contactos_recebidos=F('contactos_recebidos') + 1
        )
        return Response({'ok': True})
# ---------------------------------------------------------------------------
# Views de template (frontend)
# ---------------------------------------------------------------------------


def home_view(request):
    from apps.pagamentos.models import DestaqueAnuncio
    from apps.categorias.models import Categoria

    categorias = Categoria.objects.filter(activa=True, pai__isnull=True).order_by('ordem')

    destacados_ids = DestaqueAnuncio.objects.filter(
        activo=True,
        fim_em__gt=timezone.now(),  # FIX: excluir destaques expirados mas ainda marcados activo
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

    search = request.GET.get('search', '').strip()
    categoria_slug = request.GET.get('categoria', '').strip()
    provincia = request.GET.get('provincia', '').strip()
    preco_min = request.GET.get('preco_min', '').strip()
    preco_max = request.GET.get('preco_max', '').strip()
    condicao = request.GET.get('condicao', '').strip()
    ordering = request.GET.get('ordering', '-publicado_em')

    if search:
        queryset = queryset.filter(
            Q(titulo__icontains=search) | Q(descricao__icontains=search)
        )
    if categoria_slug:
        queryset = queryset.filter(
            Q(categoria__slug=categoria_slug) | Q(categoria__pai__slug=categoria_slug)
        )
    if provincia:
        queryset = queryset.filter(provincia__iexact=provincia)
    if preco_min:
        try:
            queryset = queryset.filter(preco__gte=float(preco_min))
        except ValueError:
            pass
    if preco_max:
        try:
            queryset = queryset.filter(preco__lte=float(preco_max))
        except ValueError:
            pass
    if condicao:
        queryset = queryset.filter(condicao=condicao)

    ordering_validos = ['publicado_em', '-publicado_em', 'preco', '-preco', '-visualizacoes']
    if ordering not in ordering_validos:
        ordering = '-publicado_em'
    queryset = queryset.order_by(ordering)

    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    page_obj.object_list = [_anuncio_para_dict(a, request) for a in page_obj]

    return render(request, 'anuncios/pesquisa.html', {
        'page_obj': page_obj,
        'categorias': Categoria.objects.filter(activa=True, pai__isnull=True).prefetch_related('subcategorias').order_by('ordem'),
        'provincias': PROVINCIAS,
        'search': search,
        'categoria_slug': categoria_slug,
        'provincia': provincia,
        'preco_min': preco_min,
        'preco_max': preco_max,
        'condicao': condicao,
        'ordering': ordering,
    })


def anuncio_detalhe_view(request, pk):
    anuncio = get_object_or_404(
        Anuncio.objects.select_related('categoria', 'utilizador')
                       .prefetch_related('imagens', 'atributos__atributo'),
        pk=pk, estado='activo'
    )
    anuncio.registar_visualizacao(utilizador=request.user)

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
@conta_activa_required
def anuncio_publicar_view(request):
    from apps.categorias.models import Categoria, AtributoCategoria

    categorias_pai = Categoria.objects.filter(activa=True, nivel=0).order_by('ordem')
    categorias_filho = Categoria.objects.filter(activa=True, pai__isnull=False).order_by('ordem')

    # Construir dicionário {categoria_id: [atributos]} para JS
    atributos_por_categoria = {}

    for sub in categorias_filho:
        # Atributos da própria subcategoria
        atributos = list(AtributoCategoria.objects.filter(categoria=sub))
        # Atributos da categoria pai (se existir)
        if sub.pai:
            atributos.extend(AtributoCategoria.objects.filter(categoria=sub.pai))

        # Remover duplicados pela chave (a chave é única por categoria)
        vistos = set()
        atributos_unicos = []
        for attr in atributos:
            if attr.chave not in vistos:
                vistos.add(attr.chave)
                atributos_unicos.append(attr)

        if atributos_unicos:
            atributos_por_categoria[sub.id] = [
                {
                    'id': attr.id,
                    'nome': attr.nome,
                    'chave': attr.chave,
                    'tipo': attr.tipo,
                    'opcoes': attr.opcoes,
                    'obrigatorio': attr.obrigatorio,
                }
                for attr in atributos_unicos
            ]

    subscricao = _get_subscricao_activa(request.user)

    return render(request, 'anuncios/publicar.html', {
        'categorias_pai': categorias_pai,
        'categorias_filho': categorias_filho,
        'atributos_json': json.dumps(atributos_por_categoria),
        'subcategorias_json': json.dumps([
            {'id': c.id, 'nome': c.nome, 'pai_id': c.pai_id}
            for c in categorias_filho
        ]),
        'subscricao': subscricao,
        'PROVINCIAS': PROVINCIAS,
    })


@login_required
def anuncio_editar_view(request, pk):
    from apps.categorias.models import Categoria, AtributoCategoria
    import json

    anuncio = get_object_or_404(Anuncio, pk=pk, utilizador=request.user)

    categorias_pai = Categoria.objects.filter(activa=True, nivel=0).order_by('ordem')
    # Usar pai__isnull=False em vez de nivel=1 para incluir todas as subcategorias
    categorias_filho = Categoria.objects.filter(activa=True, pai__isnull=False).order_by('ordem')

    # Construir atributos_por_categoria com herança (igual à view de criação)
    atributos_por_categoria = {}
    for sub in categorias_filho:
        atributos = list(AtributoCategoria.objects.filter(categoria=sub))
        if sub.pai:
            atributos.extend(AtributoCategoria.objects.filter(categoria=sub.pai))

        # Remover duplicados pela chave
        vistos = set()
        atributos_unicos = []
        for attr in atributos:
            if attr.chave not in vistos:
                vistos.add(attr.chave)
                atributos_unicos.append(attr)

        if atributos_unicos:
            atributos_por_categoria[sub.id] = [
                {
                    'id': attr.id,
                    'nome': attr.nome,
                    'chave': attr.chave,
                    'tipo': attr.tipo,
                    'opcoes': attr.opcoes,
                    'obrigatorio': attr.obrigatorio,
                }
                for attr in atributos_unicos
            ]

    subscricao = _get_subscricao_activa(request.user)

    return render(request, 'anuncios/publicar.html', {
        'anuncio': anuncio,
        'categorias_pai': categorias_pai,
        'categorias_filho': categorias_filho,
        'atributos_json': json.dumps(atributos_por_categoria),
        'subcategorias_json': json.dumps([
            {'id': c.id, 'nome': c.nome, 'pai_id': c.pai_id}
            for c in categorias_filho
        ]),
        'planos_destaque': [],  # se não houver planos de destaque avulso
        'subscricao': subscricao,
        'PROVINCIAS': PROVINCIAS,   # ← adicionar esta linha
    })


# ---------------------------------------------------------------------------
# Área do utilizador
# ---------------------------------------------------------------------------

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
    ESTADO_FILTROS = [
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
        'estado_filtros': ESTADO_FILTROS,
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


# ---------------------------------------------------------------------------
# planos
# ---------------------------------------------------------------------------


METODOS_PAGAMENTO = [
    ('mpesa',        'M-Pesa',       'smartphone'),
    ('emola',        'e-Mola',       'phone_android'),
    ('transferencia', 'Transferência', 'account_balance'),
]

FAQ_ESTATICO = [
    (
        'Posso cancelar a qualquer momento?',
        'Sim. Pode cancelar a sua subscrição quando quiser. O plano permanece activo até ao final do período pago e não há reembolsos parciais.',
    ),
    (
        'O que acontece quando a subscrição expira?',
        'Os seus anúncios ficam em estado "expirado" e deixam de aparecer nas pesquisas. Pode renovar o plano para reactivá-los automaticamente.',
    ),
    (
        'Como funciona o destaque de anúncios?',
        'Os anúncios em destaque aparecem no topo das pesquisas e na página inicial. Pode comprar destaque avulso ou usufruir dos dias incluídos no plano Pro e Empresarial.',
    ),
    (
        'Como pago via M-Pesa ou e-Mola?',
        'Após escolher o plano, introduza o seu número. Receberá uma notificação no telemóvel para aprovar o pagamento. O plano é activado imediatamente após confirmação.',
    ),
    (
        'Posso fazer upgrade ou downgrade de plano?',
        'Sim. Pode mudar de plano a qualquer momento. O upgrade é efectivo imediatamente; o downgrade aplica-se no próximo ciclo de facturação.',
    ),
    (
        'O plano Gratuito tem limitações?',
        'O plano Gratuito permite até 3 anúncios activos em simultâneo, com 3 fotos cada e duração de 30 dias. Não inclui destaque nem estatísticas avançadas.',
    ),
]


def planos_page_view(request):
    planos_publicacao = PlanoPublicacao.objects.filter(activo=True).order_by('ordem')

    subscricao_activa = None
    if request.user.is_authenticated:
        subscricao_activa = (
            SubscricaoUtilizador.objects
            .filter(utilizador=request.user, estado='activa', expira_em__gt=timezone.now())
            .select_related('plano')
            .order_by('-inicio_em')
            .first()
        )

    return render(request, 'pagamentos/planos.html', {
        'planos_publicacao':  planos_publicacao,
        'subscricao_activa':  subscricao_activa,
        'metodos_pagamento':  METODOS_PAGAMENTO,
        'faq_estatico':       FAQ_ESTATICO,
    })


def termos_condicoes(request):
    return render(request, 'anuncios/termos.html')


def politica_view(request):
    return render(request, 'anuncios/privacidade.html')


def contactos(request):
    return render(request, 'anuncios/contactos.html')


def instrucoes(request):
    return render(request, 'anuncios/instrucoes.html')