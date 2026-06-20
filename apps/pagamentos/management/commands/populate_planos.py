"""
Management command para popular os PlanoPublicacao de um site de
classificados (planos avulsos e de subscrição).

Como usar:
    1. Coloca este ficheiro em:
       <app>/management/commands/populate_planos.py
       (mesma app onde já colocaste o populate_categorias.py)

    2. Ajusta o import abaixo para o nome real da tua app.

    3. Corre:
       python manage.py populate_planos

O script é idempotente: usa update_or_create pelo "nome", podes
correr várias vezes sem duplicar.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

# AJUSTA este import para a tua app real, ex:
# from anuncios.models import PlanoPublicacao
from apps.pagamentos.models import PlanoPublicacao


# ---------------------------------------------------------------------
# Planos avulsos (paga-se por anúncio individual)
# ---------------------------------------------------------------------
PLANOS_AVULSOS = [
    {
        "nome": "Anúncio Grátis",
        "descricao": "Publica um anúncio simples, sem destaque, válido por 15 dias.",
        "tipo": "avulso",
        "preco": Decimal("0.00"),
        "max_anuncios": 1,
        "duracao_anuncio_dias": 15,
        "duracao_subscricao_dias": 0,
        "max_imagens": 3,
        "dias_destaque_incluidos": 0,
        "ordem": 0,
    },
    {
        "nome": "Anúncio Padrão",
        "descricao": "Publica 1 anúncio com mais imagens e maior duração.",
        "tipo": "avulso",
        "preco": Decimal("150.00"),
        "max_anuncios": 1,
        "duracao_anuncio_dias": 30,
        "duracao_subscricao_dias": 0,
        "max_imagens": 8,
        "dias_destaque_incluidos": 0,
        "ordem": 1,
    },
    {
        "nome": "Anúncio em Destaque",
        "descricao": "1 anúncio com 7 dias de destaque na página inicial e nos resultados de pesquisa.",
        "tipo": "avulso",
        "preco": Decimal("350.00"),
        "max_anuncios": 1,
        "duracao_anuncio_dias": 30,
        "duracao_subscricao_dias": 0,
        "max_imagens": 10,
        "dias_destaque_incluidos": 7,
        "ordem": 2,
    },
]

# ---------------------------------------------------------------------
# Planos de subscrição (pacote de créditos válido por X dias)
# ---------------------------------------------------------------------
PLANOS_SUBSCRICAO = [
    {
        "nome": "Plano Básico",
        "descricao": "Ideal para quem publica poucos anúncios por mês. Inclui 5 anúncios.",
        "tipo": "subscricao",
        "preco": Decimal("500.00"),
        "max_anuncios": 5,
        "duracao_anuncio_dias": 30,
        "duracao_subscricao_dias": 30,
        "max_imagens": 8,
        "dias_destaque_incluidos": 0,
        "ordem": 3,
    },
    {
        "nome": "Plano Profissional",
        "descricao": "Para vendedores frequentes. Inclui 20 anúncios e 3 dias de destaque em cada um.",
        "tipo": "subscricao",
        "preco": Decimal("1500.00"),
        "max_anuncios": 20,
        "duracao_anuncio_dias": 45,
        "duracao_subscricao_dias": 30,
        "max_imagens": 10,
        "dias_destaque_incluidos": 3,
        "ordem": 4,
    },
    {
        "nome": "Plano Empresarial",
        "descricao": "Para lojas e revendedores. Anúncios ilimitados durante 30 dias, com destaque incluído.",
        "tipo": "subscricao",
        "preco": Decimal("4500.00"),
        "max_anuncios": None,  # ilimitado
        "duracao_anuncio_dias": 60,
        "duracao_subscricao_dias": 30,
        "max_imagens": 15,
        "dias_destaque_incluidos": 5,
        "ordem": 5,
    },
    {
        "nome": "Plano Empresarial Anual",
        "descricao": "Mesmas vantagens do Plano Empresarial, com desconto para pagamento anual.",
        "tipo": "subscricao",
        "preco": Decimal("45000.00"),
        "max_anuncios": None,  # ilimitado
        "duracao_anuncio_dias": 60,
        "duracao_subscricao_dias": 365,
        "max_imagens": 15,
        "dias_destaque_incluidos": 5,
        "ordem": 6,
    },
]

TODOS_OS_PLANOS = PLANOS_AVULSOS + PLANOS_SUBSCRICAO


class Command(BaseCommand):
    help = "Popula a base de dados com os planos de publicação (avulsos e subscrições)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove todos os planos existentes antes de popular (CUIDADO: pode afetar anúncios/assinaturas ligados).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["limpar"]:
            self.stdout.write(self.style.WARNING("A apagar planos existentes..."))
            PlanoPublicacao.objects.all().delete()

        total = 0
        for dados in TODOS_OS_PLANOS:
            plano, criado = PlanoPublicacao.objects.update_or_create(
                nome=dados["nome"],
                defaults={
                    "descricao": dados["descricao"],
                    "tipo": dados["tipo"],
                    "preco": dados["preco"],
                    "max_anuncios": dados["max_anuncios"],
                    "duracao_anuncio_dias": dados["duracao_anuncio_dias"],
                    "duracao_subscricao_dias": dados["duracao_subscricao_dias"],
                    "max_imagens": dados["max_imagens"],
                    "dias_destaque_incluidos": dados["dias_destaque_incluidos"],
                    "ordem": dados["ordem"],
                    "activo": True,
                },
            )
            total += 1
            etiqueta = "Criado" if criado else "Atualizado"
            self.stdout.write(self.style.SUCCESS(
                f'{etiqueta}: {plano.nome} ({plano.get_tipo_display()}) — {plano.preco} MZN'
            ))

        self.stdout.write(self.style.SUCCESS(f"\nConcluído: {total} planos processados."))
