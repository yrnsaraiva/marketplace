"""
apps/anuncios/tests.py

Testes de integração para os endpoints de anúncios.
Corrige os scripts de requests ad-hoc que estavam nos ficheiros de teste.

Executar:
    python manage.py test apps.anuncios
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.users.models import User
from apps.categorias.models import Categoria, AtributoCategoria
from apps.pagamentos.models import PlanoPublicacao, SubscricaoUtilizador
from apps.anuncios.models import Anuncio

from django.utils import timezone
from datetime import timedelta


def criar_utilizador(email='test@example.com', password='Senha@1234'):
    return User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password=password,
    )


def criar_subscricao_activa(user, max_anuncios=5):
    plano = PlanoPublicacao.objects.create(
        nome='Teste', tipo='subscricao', preco=0,
        max_anuncios=max_anuncios, duracao_anuncio_dias=30,
        duracao_subscricao_dias=30, max_imagens=5,
    )
    sub = SubscricaoUtilizador.objects.create(
        utilizador=user, plano=plano,
        estado='activa',
        creditos_totais=max_anuncios,
        creditos_usados=0,
        preco_pago=0,
        inicio_em=timezone.now(),
        expira_em=timezone.now() + timedelta(days=30),
    )
    return sub


def criar_categoria(nome='Telemóveis', pai=None):
    nivel = (pai.nivel + 1) if pai else 0
    return Categoria.objects.create(
        nome=nome, slug=nome.lower().replace(' ', '-'),
        nivel=nivel, pai=pai, activa=True,
    )


class AnuncioCriarTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_utilizador()
        self.client.force_authenticate(user=self.user)
        # Categoria pai + subcategoria
        pai = criar_categoria('Electrónica')
        self.categoria = criar_categoria('Telemóveis', pai=pai)
        self.subscricao = criar_subscricao_activa(self.user)

    def test_criar_anuncio_sucesso(self):
        payload = {
            'titulo': 'iPhone 14 Pro 256GB em bom estado',
            'descricao': 'Sem riscos, bateria 90%, caixa original.',
            'preco': '85000.00',
            'preco_negociavel': True,
            'condicao': 'usado',
            'categoria': self.categoria.id,
            'provincia': 'Maputo',
            'cidade': 'Maputo',
            'bairro': 'Sommerschield',
            'atributos': [],
        }
        resp = self.client.post('/api/v1/anuncios/criar/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Anuncio.objects.count(), 1)
        self.assertEqual(Anuncio.objects.first().estado, 'activo')

    def test_criar_anuncio_sem_subscricao(self):
        """Sem subscrição activa deve devolver 400."""
        self.subscricao.estado = 'expirada'
        self.subscricao.save()

        payload = {
            'titulo': 'Samsung Galaxy S23',
            'descricao': 'Como novo, garantia activa.',
            'preco': '55000.00',
            'condicao': 'usado',
            'categoria': self.categoria.id,
            'provincia': 'Gaza',
            'cidade': 'Xai-Xai',
        }
        resp = self.client.post('/api/v1/anuncios/criar/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_criar_anuncio_atributos_obrigatorios(self):
        """Atributo obrigatório em falta deve devolver 400."""
        AtributoCategoria.objects.create(
            categoria=self.categoria, nome='Marca', chave='marca',
            tipo='texto', obrigatorio=True,
        )
        payload = {
            'titulo': 'Xiaomi Redmi Note 12',
            'descricao': 'Estado excelente.',
            'preco': '25000.00',
            'condicao': 'usado',
            'categoria': self.categoria.id,
            'provincia': 'Nampula',
            'cidade': 'Nampula',
            'atributos': [],  # Marca em falta
        }
        resp = self.client.post('/api/v1/anuncios/criar/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('atributos', resp.data)

    def test_nao_autenticado(self):
        self.client.logout()
        resp = self.client.post('/api/v1/anuncios/criar/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class AnuncioListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_utilizador()
        pai = criar_categoria('Veículos')
        self.categoria = criar_categoria('Carros', pai=pai)
        sub = criar_subscricao_activa(self.user)
        Anuncio.objects.create(
            utilizador=self.user, categoria=self.categoria,
            subscricao=sub,
            titulo='Toyota Hilux 2020', descricao='Impecável.',
            preco=2850000, condicao='usado',
            provincia='Maputo', cidade='Maputo',
            estado='activo',
        )

    def test_listar_anuncios_publico(self):
        resp = self.client.get('/api/v1/anuncios/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_anuncios_eliminados_nao_aparecem(self):
        Anuncio.objects.update(estado='eliminado')
        resp = self.client.get('/api/v1/anuncios/')
        self.assertEqual(resp.data['count'], 0)


class FavoritoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_utilizador()
        self.outro = criar_utilizador('outro@example.com')
        self.client.force_authenticate(user=self.user)
        pai = criar_categoria('Imóveis')
        cat = criar_categoria('Casas', pai=pai)
        sub = criar_subscricao_activa(self.outro)
        self.anuncio = Anuncio.objects.create(
            utilizador=self.outro, categoria=cat, subscricao=sub,
            titulo='Casa T4 Matola Rio', descricao='Espaçosa.',
            preco=4200000, condicao='novo',
            provincia='Maputo', cidade='Matola',
            estado='activo',
        )

    def test_adicionar_favorito(self):
        resp = self.client.post(f'/api/v1/anuncios/{self.anuncio.pk}/favorito/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['favorito'])

    def test_remover_favorito(self):
        self.client.post(f'/api/v1/anuncios/{self.anuncio.pk}/favorito/')
        resp = self.client.post(f'/api/v1/anuncios/{self.anuncio.pk}/favorito/')
        self.assertFalse(resp.data['favorito'])
