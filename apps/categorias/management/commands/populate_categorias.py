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
from apps.categorias.models import (Categoria, AtributoCategoria)


# ---------------------------------------------------------------------
# Estrutura de dados: cada categoria principal tem subcategorias e,
# opcionalmente, atributos próprios (aplicados à própria categoria
# onde estiverem definidos — podes adaptar para herdar nos filhos).
# ---------------------------------------------------------------------

CATEGORIAS = [
    {
        "nome": "Viaturas",
        "icone_url": "icons/viaturas.svg",
        "subcategorias": [
            {"nome": "Carros"},
            {"nome": "Motos"},
            {"nome": "Camiões e Reboques"},
            {"nome": "Barcos"},
            {"nome": "Peças e Acessórios"},
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
        "icone_url": "icons/imoveis.svg",
        "subcategorias": [
            {"nome": "Casas para Venda"},
            {"nome": "Casas para Arrendar"},
            {"nome": "Apartamentos para Venda"},
            {"nome": "Apartamentos para Arrendar"},
            {"nome": "Terrenos"},
            {"nome": "Escritórios e Espaços Comerciais"},
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
        "icone_url": "icons/eletronica.svg",
        "subcategorias": [
            {"nome": "Telemóveis"},
            {"nome": "Computadores e Portáteis"},
            {"nome": "Tablets"},
            {"nome": "TVs e Áudio"},
            {"nome": "Câmaras Fotográficas"},
            {"nome": "Acessórios"},
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
        "icone_url": "icons/casa-jardim.svg",
        "subcategorias": [
            {"nome": "Móveis"},
            {"nome": "Eletrodomésticos"},
            {"nome": "Decoração"},
            {"nome": "Jardim e Exterior"},
            {"nome": "Bricolage e Ferramentas"},
        ],
    },
    {
        "nome": "Moda e Beleza",
        "icone_url": "icons/moda.svg",
        "subcategorias": [
            {"nome": "Roupa Feminina"},
            {"nome": "Roupa Masculina"},
            {"nome": "Calçado"},
            {"nome": "Relógios e Joias"},
            {"nome": "Produtos de Beleza"},
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
        "icone_url": "icons/emprego.svg",
        "subcategorias": [
            {"nome": "Ofertas de Emprego"},
            {"nome": "Procuram-se Candidatos"},
            {"nome": "Trabalho Freelance"},
            {"nome": "Estágios"},
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
        "icone_url": "icons/servicos.svg",
        "subcategorias": [
            {"nome": "Aulas e Explicações"},
            {"nome": "Construção e Reparações"},
            {"nome": "Beleza e Bem-estar"},
            {"nome": "Eventos"},
            {"nome": "Transportes e Mudanças"},
            {"nome": "Informática e Tecnologia"},
        ],
    },
    {
        "nome": "Animais",
        "icone_url": "icons/animais.svg",
        "subcategorias": [
            {"nome": "Cães"},
            {"nome": "Gatos"},
            {"nome": "Aves"},
            {"nome": "Acessórios para Animais"},
        ],
        "atributos": [
            {"nome": "Raça", "chave": "raca", "tipo": "texto"},
            {"nome": "Idade (meses)", "chave": "idade", "tipo": "numero"},
            {"nome": "Vacinado", "chave": "vacinado", "tipo": "booleano"},
        ],
    },
    {
        "nome": "Lazer, Desporto e Hobbies",
        "icone_url": "icons/lazer.svg",
        "subcategorias": [
            {"nome": "Material Desportivo"},
            {"nome": "Bicicletas"},
            {"nome": "Instrumentos Musicais"},
            {"nome": "Livros e Revistas"},
            {"nome": "Brinquedos e Jogos"},
        ],
    },
    {
        "nome": "Negócios e Equipamentos",
        "icone_url": "icons/negocios.svg",
        "subcategorias": [
            {"nome": "Equipamento Industrial"},
            {"nome": "Equipamento de Escritório"},
            {"nome": "Negócios à Venda"},
            {"nome": "Matérias-primas"},
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
                        "icone_url": sub.get("icone_url", ""),
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