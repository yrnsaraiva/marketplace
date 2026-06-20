"""
Management command para popular a árvore de Categorias e respetivos
AtributoCategoria de um site de classificados.

Como usar:
    1. Coloca este ficheiro em:
       <app>/management/commands/populate_categorias.py
       (cria as pastas management/ e management/commands/ com um
       __init__.py vazio em cada uma, se ainda não existirem)

    2. Ajusta o import abaixo ("from core.models import ...") para
       o nome real da tua app.

    3. Corre:
       python manage.py populate_categorias

O script é idempotente: podes correr várias vezes sem duplicar dados.
"""

from django.db import transaction
from django.utils.text import slugify
from django.core.management.base import BaseCommand

# AJUSTA este import para a tua app real, ex:
# from anuncios.models import Categoria, AtributoCategoria
from apps.categorias.models import Categoria, AtributoCategoria


# ---------------------------------------------------------------------
# Estrutura de dados: cada categoria principal tem subcategorias e,
# opcionalmente, atributos próprios (aplicados à própria categoria
# onde estiverem definidos — podes adaptar para herdar nos filhos).
# ---------------------------------------------------------------------

CATEGORIAS = [
    {
        "nome": "Viaturas",
        "icone_url": "directions_car",
        "subcategorias": [
            {"nome": "Carros", "icone_url": "directions_car"},
            {"nome": "Motos", "icone_url": "two_wheeler"},
            {"nome": "Camiões e Reboques", "icone_url": "local_shipping"},
            {"nome": "Barcos", "icone_url": "directions_boat"},
            {"nome": "Peças e Acessórios", "icone_url": "settings_input_component"},
        ],
        "atributos": [
            {"nome": "Marca", "chave": "marca", "tipo": "texto", "obrigatorio": True},
            {"nome": "Modelo", "chave": "modelo", "tipo": "texto", "obrigatorio": True},
            {"nome": "Ano", "chave": "ano", "tipo": "numero", "obrigatorio": True},
            {"nome": "Quilometragem (km)", "chave": "quilometragem", "tipo": "numero"},
            {
                "nome": "Combustível",
                "chave": "combustivel",
                "tipo": "lista",
                "opcoes": ["Gasolina", "Gasóleo", "Híbrido", "Elétrico", "GPL"],
            },
            {
                "nome": "Câmbio",
                "chave": "cambio",
                "tipo": "lista",
                "opcoes": ["Manual", "Automático"],
            },
        ],
    },
    {
        "nome": "Imóveis",
        "icone_url": "home_work",
        "subcategorias": [
            {"nome": "Casas para Venda", "icone_url": "house"},
            {"nome": "Casas para Arrendar", "icone_url": "key"},
            {"nome": "Apartamentos para Venda", "icone_url": "apartment"},
            {"nome": "Apartamentos para Arrendar", "icone_url": "domain"},
            {"nome": "Terrenos", "icone_url": "landscape"},
            {"nome": "Escritórios e Espaços Comerciais", "icone_url": "storefront"},
        ],
        "atributos": [
            {"nome": "Tipologia", "chave": "tipologia", "tipo": "lista",
             "opcoes": ["T0", "T1", "T2", "T3", "T4", "T5+"]},
            {"nome": "Área (m²)", "chave": "area", "tipo": "numero"},
            {"nome": "Casas de banho", "chave": "casas_banho", "tipo": "numero"},
            {"nome": "Mobilado", "chave": "mobilado", "tipo": "booleano"},
        ],
    },
    {
        "nome": "Eletrónica",
        "icone_url": "devices",
        "subcategorias": [
            {"nome": "Telemóveis", "icone_url": "smartphone"},
            {"nome": "Computadores e Portáteis", "icone_url": "laptop_mac"},
            {"nome": "Tablets", "icone_url": "tablet_mac"},
            {"nome": "TVs e Áudio", "icone_url": "tv"},
            {"nome": "Câmaras Fotográficas", "icone_url": "photo_camera"},
            {"nome": "Acessórios", "icone_url": "cable"},
        ],
        "atributos": [
            {"nome": "Marca", "chave": "marca", "tipo": "texto", "obrigatorio": True},
            {
                "nome": "Estado",
                "chave": "estado",
                "tipo": "lista",
                "opcoes": ["Novo", "Usado - Como novo", "Usado - Bom", "Usado - Razoável", "Para peças"],
                "obrigatorio": True,
            },
            {"nome": "Garantia", "chave": "garantia", "tipo": "booleano"},
        ],
    },
    {
        "nome": "Casa e Jardim",
        "icone_url": "yard",
        "subcategorias": [
            {"nome": "Móveis", "icone_url": "chair"},
            {"nome": "Eletrodomésticos", "icone_url": "kitchen"},
            {"nome": "Decoração", "icone_url": "interests"},
            {"nome": "Jardim e Exterior", "icone_url": "deck"},
            {"nome": "Bricolage e Ferramentas", "icone_url": "construction"},
        ],
    },
    {
        "nome": "Moda e Beleza",
        "icone_url": "checkroom",
        "subcategorias": [
            {"nome": "Roupa Feminina", "icone_url": "checkroom"},
            {"nome": "Roupa Masculina", "icone_url": "apparel"},
            {"nome": "Calçado", "icone_url": "footprint"},
            {"nome": "Relógios e Joias", "icone_url": "watch"},
            {"nome": "Produtos de Beleza", "icone_url": "spa"},
        ],
        "atributos": [
            {
                "nome": "Tamanho",
                "chave": "tamanho",
                "tipo": "lista",
                "opcoes": ["XS", "S", "M", "L", "XL", "XXL"],
            },
            {
                "nome": "Condição",
                "chave": "condicao",
                "tipo": "lista",
                "opcoes": ["Novo com etiqueta", "Novo sem etiqueta", "Usado"],
            },
        ],
    },
    {
        "nome": "Emprego",
        "icone_url": "work",
        "subcategorias": [
            {"nome": "Ofertas de Emprego", "icone_url": "work"},
            {"nome": "Procuram-se Candidatos", "icone_url": "person_search"},
            {"nome": "Trabalho Freelance", "icone_url": "laptop_chromebook"},
            {"nome": "Estágios", "icone_url": "school"},
        ],
        "atributos": [
            {
                "nome": "Tipo de contrato",
                "chave": "tipo_contrato",
                "tipo": "lista",
                "opcoes": ["Full-time", "Part-time", "Freelance", "Estágio", "Temporário"],
            },
            {"nome": "Salário (referência)", "chave": "salario", "tipo": "numero"},
            {"nome": "Empresa", "chave": "empresa", "tipo": "texto"},
        ],
    },
    {
        "nome": "Serviços",
        "icone_url": "handyman",
        "subcategorias": [
            {"nome": "Aulas e Explicações", "icone_url": "menu_book"},
            {"nome": "Construção e Reparações", "icone_url": "build"},
            {"nome": "Beleza e Bem-estar", "icone_url": "self_care"},
            {"nome": "Eventos", "icone_url": "celebration"},
            {"nome": "Transportes e Mudanças", "icone_url": "local_shipping"},
            {"nome": "Informática e Tecnologia", "icone_url": "computer"},
        ],
    },
    {
        "nome": "Animais",
        "icone_url": "pets",
        "subcategorias": [
            {"nome": "Cães", "icone_url": "pets"},
            {"nome": "Gatos", "icone_url": "cruelty_free"},
            {"nome": "Aves", "icone_url": "flutter_dash"},
            {"nome": "Acessórios para Animais", "icone_url": "shopping_basket"},
        ],
        "atributos": [
            {"nome": "Raça", "chave": "raca", "tipo": "texto"},
            {"nome": "Idade (meses)", "chave": "idade", "tipo": "numero"},
            {"nome": "Vacinado", "chave": "vacinado", "tipo": "booleano"},
        ],
    },
    {
        "nome": "Lazer, Desporto e Hobbies",
        "icone_url": "sports_soccer",
        "subcategorias": [
            {"nome": "Material Desportivo", "icone_url": "sports_soccer"},
            {"nome": "Bicicletas", "icone_url": "directions_bike"},
            {"nome": "Instrumentos Musicais", "icone_url": "music_note"},
            {"nome": "Livros e Revistas", "icone_url": "menu_book"},
            {"nome": "Brinquedos e Jogos", "icone_url": "toys"},
        ],
    },
    {
        "nome": "Negócios e Equipamentos",
        "icone_url": "business_center",
        "subcategorias": [
            {"nome": "Equipamento Industrial", "icone_url": "precision_manufacturing"},
            {"nome": "Equipamento de Escritório", "icone_url": "print"},
            {"nome": "Negócios à Venda", "icone_url": "storefront"},
            {"nome": "Matérias-primas", "icone_url": "inventory_2"},
        ],
    },
]


class Command(BaseCommand):
    help = "Popula a base de dados com categorias, subcategorias e atributos para o site de classificados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove todas as categorias existentes antes de popular (CUIDADO: apaga anúncios ligados em cascata).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["limpar"]:
            self.stdout.write(self.style.WARNING("A apagar categorias existentes..."))
            Categoria.objects.all().delete()

        total_categorias = 0
        total_subcategorias = 0
        total_atributos = 0

        for ordem_principal, dados in enumerate(CATEGORIAS):
            categoria_pai, criada = Categoria.objects.update_or_create(
                slug=slugify(dados["nome"]),
                defaults={
                    "nome": dados["nome"],
                    "icone_url": dados.get("icone_url", ""),
                    "ordem": ordem_principal,
                    "pai": None,
                },
            )
            total_categorias += 1
            self.stdout.write(
                self.style.SUCCESS(f'{"Criada" if criada else "Atualizada"}: {categoria_pai.nome}')
            )

            # Subcategorias
            for ordem_sub, sub in enumerate(dados.get("subcategorias", [])):
                slug_sub = slugify(f'{dados["nome"]}-{sub["nome"]}')
                subcategoria, criada_sub = Categoria.objects.update_or_create(
                    slug=slug_sub,
                    defaults={
                        "nome": sub["nome"],
                        "icone_url": sub.get("icone_url", dados.get("icone_url", "")),
                        "ordem": ordem_sub,
                        "pai": categoria_pai,
                    },
                )
                total_subcategorias += 1
                self.stdout.write(f'   └─ {subcategoria.nome}')

            # Atributos (aplicados à categoria principal)
            for atributo in dados.get("atributos", []):
                _, criado_attr = AtributoCategoria.objects.update_or_create(
                    categoria=categoria_pai,
                    chave=atributo["chave"],
                    defaults={
                        "nome": atributo["nome"],
                        "tipo": atributo.get("tipo", "texto"),
                        "opcoes": atributo.get("opcoes"),
                        "obrigatorio": atributo.get("obrigatorio", False),
                    },
                )
                total_atributos += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nConcluído: {total_categorias} categorias principais, "
            f"{total_subcategorias} subcategorias, {total_atributos} atributos."
        ))