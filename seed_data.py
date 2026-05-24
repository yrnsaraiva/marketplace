"""
Management command Django para seed de dados de teste.

Estrutura esperada no projecto:
    <app>/management/commands/seed.py

Execução:
    python manage.py seed
    python manage.py seed --flush    # apaga tudo antes de inserir
    python manage.py seed --usuarios-apenas
"""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

# ── Importa os modelos do projecto ──────────────────────────────────────────
from apps.categorias.models import Categoria, AtributoCategoria
from apps.anuncios.models import Anuncio, AtributoAnuncio, ImagemAnuncio, Favorito
from apps.pagamentos.models import (
    PlanoPublicacao,
    PlanoDestaque,
    SubscricaoUtilizador,
    Pagamento,
    DestaqueAnuncio,
)

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────────

def ago(days: int):
    return timezone.now() - timedelta(days=days)


def daqui(days: int):
    return timezone.now() + timedelta(days=days)


# ── Command ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Popula a base de dados com dados de teste para desenvolvimento."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Remove todos os dados existentes antes de inserir.",
        )
        parser.add_argument(
            "--usuarios-apenas",
            action="store_true",
            help="Cria apenas utilizadores de teste.",
        )

    # ── handle ────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        self._criar_utilizadores()

        if not options["usuarios_apenas"]:
            self._criar_categorias()
            self._criar_planos()
            self._criar_subscricoes()
            self._criar_pagamentos()
            self._criar_anuncios()
            self._criar_destaques()

        self.stdout.write(self.style.SUCCESS("\n✅  Seed concluído com sucesso!\n"))
        self._resumo()

    # ── flush ─────────────────────────────────────────────────────────────────

    def _flush(self):
        self.stdout.write(self.style.WARNING("⚠️  A apagar dados existentes…"))
        DestaqueAnuncio.objects.all().delete()
        Favorito.objects.all().delete()
        AtributoAnuncio.objects.all().delete()
        ImagemAnuncio.objects.all().delete()
        Anuncio.objects.all().delete()
        Pagamento.objects.all().delete()
        SubscricaoUtilizador.objects.all().delete()
        PlanoDestaque.objects.all().delete()
        PlanoPublicacao.objects.all().delete()
        AtributoCategoria.objects.all().delete()
        Categoria.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    # ── utilizadores ─────────────────────────────────────────────────────────

    def _criar_utilizadores(self):
        self.stdout.write("👤  Utilizadores…")

        dados = [
            dict(
                username="ana.machava",
                first_name="Ana",
                last_name="Machava",
                email="ana.machava@email.co.mz",
                telefone="+258841234567",
                provincia="Maputo",
                cidade="Maputo",
                papel="vendedor",
                telefone_verificado=True,
                email_verificado=True,
                avaliacao_media=4.5,
                total_anuncios=5,
            ),
            dict(
                username="carlos.munguambe",
                first_name="Carlos",
                last_name="Munguambe",
                email="carlos.munguambe@gmail.com",
                telefone="+258861122334",
                provincia="Gaza",
                cidade="Xai-Xai",
                papel="vendedor",
                telefone_verificado=True,
                email_verificado=False,
                avaliacao_media=4.0,
                total_anuncios=3,
            ),
            dict(
                username="fatima.uque",
                first_name="Fátima",
                last_name="Uque",
                email="fatima.uque@hotmail.com",
                telefone="+258871234567",
                provincia="Sofala",
                cidade="Beira",
                papel="comprador",
                telefone_verificado=False,
                email_verificado=True,
                avaliacao_media=0.0,
                total_anuncios=0,
            ),
            dict(
                username="joao.nhatave",
                first_name="João",
                last_name="Nhatave",
                email="joao.nhatave@email.com",
                telefone="+258851234560",
                provincia="Nampula",
                cidade="Nampula",
                papel="vendedor",
                telefone_verificado=True,
                email_verificado=True,
                avaliacao_media=4.8,
                total_anuncios=8,
            ),
            dict(
                username="pedro.cossa",
                first_name="Pedro",
                last_name="Cossa",
                email="pedro.cossa@gmail.com",
                telefone="+258821234567",
                provincia="Maputo",
                cidade="Matola",
                papel="comprador",
                telefone_verificado=False,
                email_verificado=False,
                bloqueado=True,
                motivo_bloqueio="Spam de anúncios duplicados.",
                avaliacao_media=0.0,
                total_anuncios=0,
            ),
        ]

        self._users = {}
        for d in dados:
            username = d.pop("username")
            user, created = User.objects.get_or_create(
                username=username,
                defaults=d,
            )
            if created:
                user.set_password("password123")
                user.save()
            self._users[username] = user

        self.stdout.write(f"   → {len(self._users)} utilizadores")

    # ── categorias ────────────────────────────────────────────────────────────

    def _criar_categorias(self):
        self.stdout.write("📂  Categorias…")

        # Raiz
        raiz = {}
        raiz_dados = [
            ("Veículos",         "veiculos",         "icons/veiculos.svg",    1),
            ("Imóveis",          "imoveis",           "icons/imoveis.svg",     2),
            ("Electrónica",      "electronica",       "icons/electronica.svg", 3),
            ("Moda & Vestuário", "moda-vestuario",    "icons/moda.svg",        4),
            ("Emprego",          "emprego",           "icons/emprego.svg",     5),
        ]
        for nome, slug, icone, ordem in raiz_dados:
            cat, _ = Categoria.objects.get_or_create(
                slug=slug,
                defaults=dict(nome=nome, icone_url=icone, ordem=ordem, activa=True, nivel=0),
            )
            raiz[slug] = cat

        # Sub-categorias
        sub_dados = [
            ("Carros",        "carros",        "icons/carros.svg",        1, raiz["veiculos"]),
            ("Motas",         "motas",         "icons/motas.svg",         2, raiz["veiculos"]),
            ("Apartamentos",  "apartamentos",  "icons/apartamentos.svg",  1, raiz["imoveis"]),
            ("Casas",         "casas",         "icons/casas.svg",         2, raiz["imoveis"]),
            ("Telemóveis",    "telemoveis",     "icons/telemoveis.svg",    1, raiz["electronica"]),
            ("Computadores",  "computadores",  "icons/computadores.svg",  2, raiz["electronica"]),
        ]
        self._cats = {}
        for nome, slug, icone, ordem, pai in sub_dados:
            cat, _ = Categoria.objects.get_or_create(
                slug=slug,
                defaults=dict(nome=nome, icone_url=icone, ordem=ordem, activa=True, nivel=1, pai=pai),
            )
            self._cats[slug] = cat

        # Atributos
        atributos = [
            # (nome, chave, tipo, opcoes, obrigatorio, cat_slug)
            ("Marca",         "marca",         "text",   None,                                                      True,  "carros"),
            ("Modelo",        "modelo",        "text",   None,                                                      True,  "carros"),
            ("Ano",           "ano",           "number", None,                                                      True,  "carros"),
            ("Quilometragem", "quilometragem", "number", None,                                                      False, "carros"),
            ("Combustível",   "combustivel",   "select", json.dumps(["Gasolina","Gasóleo","Híbrido","Eléctrico"]), True,  "carros"),
            ("Transmissão",   "transmissao",   "select", json.dumps(["Manual","Automático"]),                      False, "carros"),
            ("Tipologia",     "tipologia",     "select", json.dumps(["T1","T2","T3","T4","T5+"]),                  True,  "apartamentos"),
            ("Área (m²)",     "area_m2",       "number", None,                                                      False, "apartamentos"),
            ("Marca",         "marca",         "text",   None,                                                      True,  "telemoveis"),
            ("Modelo",        "modelo",        "text",   None,                                                      True,  "telemoveis"),
            ("Armazenamento", "armazenamento", "select", json.dumps(["64GB","128GB","256GB","512GB"]),              False, "telemoveis"),
            ("Estado bateria","estado_bateria","select", json.dumps(["Excelente","Bom","Regular"]),                False, "telemoveis"),
            ("Marca",         "marca",         "text",   None,                                                      True,  "computadores"),
            ("Modelo",        "modelo",        "text",   None,                                                      True,  "computadores"),
        ]
        self._atribs = {}
        for nome, chave, tipo, opcoes, obrig, cat_slug in atributos:
            a, _ = AtributoCategoria.objects.get_or_create(
                chave=chave, categoria=self._cats[cat_slug],
                defaults=dict(nome=nome, tipo=tipo, opcoes=opcoes, obrigatorio=obrig),
            )
            self._atribs[(cat_slug, chave)] = a

        total = Categoria.objects.count()
        self.stdout.write(f"   → {total} categorias")

    # ── planos ────────────────────────────────────────────────────────────────

    def _criar_planos(self):
        self.stdout.write("💳  Planos…")

        pub = [
            dict(nome="Gratuito",     descricao="Até 3 anúncios gratuitamente.",
                 tipo="gratuito", preco=0,    max_anuncios=3,    duracao_anuncio_dias=30,
                 duracao_subscricao_dias=30, max_imagens=3,  dias_destaque_incluidos=0,  activo=True, ordem=1),
            dict(nome="Básico",       descricao="Até 10 anúncios activos com 5 imagens cada.",
                 tipo="pago",     preco=199,  max_anuncios=10,   duracao_anuncio_dias=60,
                 duracao_subscricao_dias=30, max_imagens=5,  dias_destaque_incluidos=0,  activo=True, ordem=2),
            dict(nome="Pro",          descricao="Anúncios ilimitados, 10 imagens e 7 dias de destaque incluídos.",
                 tipo="pago",     preco=499,  max_anuncios=None, duracao_anuncio_dias=90,
                 duracao_subscricao_dias=30, max_imagens=10, dias_destaque_incluidos=7,  activo=True, ordem=3),
            dict(nome="Empresarial",  descricao="Solução completa para negócios. Suporte prioritário.",
                 tipo="pago",     preco=999,  max_anuncios=None, duracao_anuncio_dias=180,
                 duracao_subscricao_dias=30, max_imagens=15, dias_destaque_incluidos=30, activo=True, ordem=4),
        ]
        self._planos_pub = {}
        for d in pub:
            nome = d["nome"]
            p, _ = PlanoPublicacao.objects.get_or_create(nome=nome, defaults=d)
            self._planos_pub[nome] = p

        dest = [
            dict(nome="Destaque 3 Dias",  descricao="Posição de destaque por 3 dias.",  duracao_dias=3,  preco=99,  tipo="basico",   boost_visualizacoes=2,  activo=True, ordem=1),
            dict(nome="Destaque 7 Dias",  descricao="Posição de destaque por 7 dias.",  duracao_dias=7,  preco=199, tipo="standard", boost_visualizacoes=5,  activo=True, ordem=2),
            dict(nome="Destaque 15 Dias", descricao="Posição de destaque por 15 dias.", duracao_dias=15, preco=349, tipo="premium",  boost_visualizacoes=10, activo=True, ordem=3),
            dict(nome="Destaque 30 Dias", descricao="Máxima visibilidade por 30 dias.", duracao_dias=30, preco=599, tipo="premium",  boost_visualizacoes=20, activo=True, ordem=4),
        ]
        self._planos_dest = {}
        for d in dest:
            nome = d["nome"]
            p, _ = PlanoDestaque.objects.get_or_create(nome=nome, defaults=d)
            self._planos_dest[nome] = p

        self.stdout.write(f"   → {len(pub)} planos de publicação, {len(dest)} planos de destaque")

    # ── subscrições ───────────────────────────────────────────────────────────

    def _criar_subscricoes(self):
        self.stdout.write("📋  Subscrições…")

        dados = [
            dict(utilizador=self._users["ana.machava"],    plano=self._planos_pub["Gratuito"],
                 estado="activo",   creditos_totais=3,    creditos_usados=2, preco_pago=0,
                 inicio_em=ago(30), expira_em=daqui(30)),
            dict(utilizador=self._users["carlos.munguambe"], plano=self._planos_pub["Básico"],
                 estado="activo",   creditos_totais=10,   creditos_usados=3, preco_pago=199,
                 inicio_em=ago(7),  expira_em=daqui(30)),
            dict(utilizador=self._users["joao.nhatave"],   plano=self._planos_pub["Pro"],
                 estado="activo",   creditos_totais=None, creditos_usados=8, preco_pago=499,
                 inicio_em=ago(30), expira_em=daqui(60)),
            dict(utilizador=self._users["fatima.uque"],    plano=self._planos_pub["Gratuito"],
                 estado="expirado", creditos_totais=3,    creditos_usados=3, preco_pago=0,
                 inicio_em=ago(30), expira_em=ago(7)),
        ]

        self._subs = {}
        for d in dados:
            user = d["utilizador"]
            sub, _ = SubscricaoUtilizador.objects.get_or_create(
                utilizador=user, plano=d["plano"],
                defaults=d,
            )
            self._subs[user.username] = sub

        self.stdout.write(f"   → {len(self._subs)} subscrições")

    # ── pagamentos ────────────────────────────────────────────────────────────

    def _criar_pagamentos(self):
        self.stdout.write("💰  Pagamentos…")

        admin = User.objects.filter(is_superuser=True).first()

        dados = [
            dict(subscricao=self._subs["carlos.munguambe"], metodo="mpesa",
                 estado="confirmado", valor=199, referencia_externa="MPESA-TEST-001",
                 telefone_pagamento="+258861122334",
                 confirmado_em=ago(7), confirmado_por=admin,
                 resposta_gateway=json.dumps({"code": "0", "desc": "OK"})),
            dict(subscricao=self._subs["joao.nhatave"], metodo="mpesa",
                 estado="confirmado", valor=499, referencia_externa="MPESA-TEST-002",
                 telefone_pagamento="+258851234560",
                 confirmado_em=ago(7), confirmado_por=admin,
                 resposta_gateway=json.dumps({"code": "0", "desc": "OK"})),
            dict(subscricao=self._subs["fatima.uque"], metodo="emola",
                 estado="pendente", valor=199, referencia_externa="EMOLA-TEST-003",
                 telefone_pagamento="+258871234567",
                 confirmado_em=None, confirmado_por=None,
                 resposta_gateway=json.dumps({})),
            dict(subscricao=self._subs["ana.machava"], metodo="transferencia",
                 estado="rejeitado", valor=999, referencia_externa="TRF-TEST-004",
                 telefone_pagamento="+258841234567",
                 confirmado_em=None, confirmado_por=None,
                 resposta_gateway=json.dumps({"code": "ERR", "desc": "Saldo insuficiente"})),
        ]

        for d in dados:
            Pagamento.objects.get_or_create(
                referencia_externa=d["referencia_externa"],
                defaults=d,
            )

        self.stdout.write(f"   → {len(dados)} pagamentos")

    # ── anúncios ──────────────────────────────────────────────────────────────

    def _criar_anuncios(self):
        self.stdout.write("📢  Anúncios…")

        ana      = self._users["ana.machava"]
        carlos   = self._users["carlos.munguambe"]
        fatima   = self._users["fatima.uque"]
        joao     = self._users["joao.nhatave"]

        sub_ana    = self._subs["ana.machava"]
        sub_carlos = self._subs["carlos.munguambe"]
        sub_joao   = self._subs["joao.nhatave"]

        carros       = self._cats["carros"]
        apartamentos = self._cats["apartamentos"]
        telemoveis   = self._cats["telemoveis"]
        computadores = self._cats["computadores"]
        motas        = self._cats["motas"]
        casas        = self._cats["casas"]

        anuncios_dados = [
            # ── PUBLICADOS ──────────────────────────────────────────────────
            dict(
                titulo="Toyota Hilux 2020 — impecável",
                descricao=(
                    "Hilux SRV 2.8 Diesel, automático, 4x4, 45.000 km. "
                    "Único dono, revisões em dia. Cor branca, vidros eléctricos, "
                    "ar condicionado, câmara de ré."
                ),
                preco=2850000, preco_negociavel=True, condicao="usado",
                provincia="Maputo", cidade="Maputo", bairro="Sommerschield",
                estado="publicado", visualizacoes=312, contactos_recebidos=18,
                auto_renovar=True, publicado_em=ago(30),
                expira_em=daqui(30), categoria=carros, subscricao=sub_ana, utilizador=ana,
                _atributos={"marca": "Toyota", "modelo": "Hilux SRV", "ano": "2020",
                            "quilometragem": "45000", "combustivel": "Gasóleo", "transmissao": "Automático"},
                _imagens=["anuncios/hilux_1.jpg", "anuncios/hilux_2.jpg", "anuncios/hilux_3.jpg"],
            ),
            dict(
                titulo="Apartamento T3 Sommerschield II",
                descricao=(
                    "Apartamento moderno com 3 quartos, 2 casas de banho, sala espaçosa, "
                    "cozinha equipada e varanda com vista para o jardim. "
                    "Condomínio fechado, segurança 24h."
                ),
                preco=7500000, preco_negociavel=False, condicao="usado",
                provincia="Maputo", cidade="Maputo", bairro="Sommerschield II",
                estado="publicado", visualizacoes=540, contactos_recebidos=25,
                auto_renovar=True, publicado_em=ago(30),
                expira_em=daqui(30), categoria=apartamentos, subscricao=sub_ana, utilizador=ana,
                _atributos={"tipologia": "T3", "area_m2": "140"},
                _imagens=["anuncios/apto_t3_1.jpg", "anuncios/apto_t3_2.jpg"],
            ),
            dict(
                titulo="iPhone 14 Pro 256GB",
                descricao=(
                    "iPhone 14 Pro em excelente estado. Bateria 91%, sem riscos, "
                    "caixa original e todos os acessórios incluídos. Comprado no exterior."
                ),
                preco=85000, preco_negociavel=True, condicao="usado",
                provincia="Gaza", cidade="Xai-Xai", bairro="Centro",
                estado="publicado", visualizacoes=89, contactos_recebidos=7,
                auto_renovar=False, publicado_em=ago(7),
                expira_em=daqui(30), categoria=telemoveis, subscricao=sub_carlos, utilizador=carlos,
                _atributos={"marca": "Apple", "modelo": "iPhone 14 Pro",
                            "armazenamento": "256GB", "estado_bateria": "Excelente"},
                _imagens=["anuncios/iphone14_1.jpg", "anuncios/iphone14_2.jpg"],
            ),
            dict(
                titulo="Honda CB 300R 2022",
                descricao=(
                    "Mota em óptimas condições, 12.000 km, cor preta. "
                    "Documentação em dia. Vendo por não ter mais tempo para usar."
                ),
                preco=220000, preco_negociavel=True, condicao="usado",
                provincia="Nampula", cidade="Nampula", bairro="Mutauanha",
                estado="publicado", visualizacoes=203, contactos_recebidos=14,
                auto_renovar=True, publicado_em=ago(30),
                expira_em=daqui(60), categoria=motas, subscricao=sub_joao, utilizador=joao,
                _atributos={},
                _imagens=["anuncios/honda_cb_1.jpg", "anuncios/honda_cb_2.jpg"],
            ),
            dict(
                titulo="Laptop Dell XPS 15 — i7 32GB",
                descricao=(
                    "Dell XPS 15 9510, Intel i7-11800H, 32GB RAM, 1TB SSD, "
                    "ecrã 4K OLED. Ideal para designers e programadores."
                ),
                preco=195000, preco_negociavel=False, condicao="usado",
                provincia="Nampula", cidade="Nampula", bairro="Cidade Alta",
                estado="publicado", visualizacoes=157, contactos_recebidos=9,
                auto_renovar=True, publicado_em=ago(7),
                expira_em=daqui(60), categoria=computadores, subscricao=sub_joao, utilizador=joao,
                _atributos={"marca": "Dell", "modelo": "XPS 15"},
                _imagens=["anuncios/dell_xps_1.jpg"],
            ),
            # ── PENDENTE ────────────────────────────────────────────────────
            dict(
                titulo="Casa T4 Matola Rio",
                descricao=(
                    "Casa com 4 quartos, 2 wc, sala de estar e jantar separadas, "
                    "cozinha ampla, garagem para 2 carros e quintal grande."
                ),
                preco=4200000, preco_negociavel=True, condicao="novo",
                provincia="Maputo", cidade="Matola", bairro="Matola Rio",
                estado="pendente", visualizacoes=0, contactos_recebidos=0,
                auto_renovar=False, publicado_em=None,
                expira_em=None, categoria=casas, subscricao=sub_carlos, utilizador=carlos,
                _atributos={},
                _imagens=[],
            ),
            # ── REJEITADO ───────────────────────────────────────────────────
            dict(
                titulo="Samsung Galaxy S23 Ultra",
                descricao="Samsung com problema no ecrã. Vendo para peças.",
                preco=35000, preco_negociavel=True, condicao="usado",
                provincia="Sofala", cidade="Beira", bairro="Munhava",
                estado="rejeitado",
                motivo_rejeicao="Descrição insuficiente. Adicione mais detalhes e fotos.",
                visualizacoes=0, contactos_recebidos=0,
                auto_renovar=False, publicado_em=None,
                expira_em=None, categoria=telemoveis, subscricao=None, utilizador=fatima,
                _atributos={"marca": "Samsung", "modelo": "Galaxy S23 Ultra"},
                _imagens=[],
            ),
            # ── EXPIRADO ────────────────────────────────────────────────────
            dict(
                titulo="Volkswagen Polo 2018 — 1.6 Comfortline",
                descricao=(
                    "Polo automático, cor cinza metálico, 62.000 km. "
                    "Ar condicionado, sensor de estacionamento, ecrã táctil."
                ),
                preco=950000, preco_negociavel=True, condicao="usado",
                provincia="Maputo", cidade="Maputo", bairro="Julius Nyerere",
                estado="expirado", visualizacoes=88, contactos_recebidos=3,
                auto_renovar=False, publicado_em=ago(30),
                expira_em=ago(7), categoria=carros, subscricao=sub_ana, utilizador=ana,
                _atributos={"marca": "Volkswagen", "modelo": "Polo",
                            "ano": "2018", "quilometragem": "62000",
                            "combustivel": "Gasolina", "transmissao": "Automático"},
                _imagens=["anuncios/polo_2018_1.jpg", "anuncios/polo_2018_2.jpg"],
            ),
        ]

        self._anuncios = {}
        for d in anuncios_dados:
            atributos_vals = d.pop("_atributos")
            imagens_vals   = d.pop("_imagens")

            anuncio, created = Anuncio.objects.get_or_create(
                titulo=d["titulo"], utilizador=d["utilizador"],
                defaults=d,
            )

            if created:
                # Atributos do anúncio
                cat_slug = anuncio.categoria.slug
                for chave, valor in atributos_vals.items():
                    atrib = self._atribs.get((cat_slug, chave))
                    if atrib:
                        AtributoAnuncio.objects.get_or_create(
                            anuncio=anuncio, atributo=atrib,
                            defaults={"valor": valor},
                        )

                # Imagens
                for i, caminho in enumerate(imagens_vals):
                    ImagemAnuncio.objects.get_or_create(
                        anuncio=anuncio, imagem=caminho,
                        defaults={"ordem": i + 1, "principal": i == 0},
                    )

            self._anuncios[anuncio.titulo] = anuncio

        # Favoritos
        favs = [
            (self._users["fatima.uque"],      "Toyota Hilux 2020 — impecável"),
            (self._users["fatima.uque"],      "Apartamento T3 Sommerschield II"),
            (self._users["ana.machava"],      "Honda CB 300R 2022"),
            (self._users["carlos.munguambe"], "Laptop Dell XPS 15 — i7 32GB"),
            (self._users["joao.nhatave"],     "Toyota Hilux 2020 — impecável"),
        ]
        for user, titulo in favs:
            anuncio = self._anuncios.get(titulo)
            if anuncio:
                Favorito.objects.get_or_create(utilizador=user, anuncio=anuncio)

        self.stdout.write(f"   → {len(self._anuncios)} anúncios, {len(favs)} favoritos")

    # ── destaques ─────────────────────────────────────────────────────────────

    def _criar_destaques(self):
        self.stdout.write("✨  Destaques…")

        dados = [
            dict(anuncio=self._anuncios["Toyota Hilux 2020 — impecável"],
                 plano_destaque=self._planos_dest["Destaque 7 Dias"],
                 origem="pagamento", activo=True, inicio_em=ago(7), fim_em=daqui(30)),
            dict(anuncio=self._anuncios["Honda CB 300R 2022"],
                 plano_destaque=self._planos_dest["Destaque 3 Dias"],
                 origem="subscricao", activo=True, inicio_em=ago(7), fim_em=daqui(30)),
            dict(anuncio=self._anuncios["Volkswagen Polo 2018 — 1.6 Comfortline"],
                 plano_destaque=self._planos_dest["Destaque 3 Dias"],
                 origem="pagamento", activo=False, inicio_em=ago(30), fim_em=ago(7)),
        ]

        for d in dados:
            DestaqueAnuncio.objects.get_or_create(
                anuncio=d["anuncio"], plano_destaque=d["plano_destaque"],
                defaults=d,
            )

        self.stdout.write(f"   → {len(dados)} destaques")

    # ── resumo ────────────────────────────────────────────────────────────────

    def _resumo(self):
        linhas = [
            ("👤 Utilizadores",        User.objects.count()),
            ("📂 Categorias",           Categoria.objects.count()),
            ("💳 Planos publicação",    PlanoPublicacao.objects.count()),
            ("⭐ Planos destaque",      PlanoDestaque.objects.count()),
            ("📋 Subscrições",          SubscricaoUtilizador.objects.count()),
            ("💰 Pagamentos",           Pagamento.objects.count()),
            ("📢 Anúncios",             Anuncio.objects.count()),
            ("❤️  Favoritos",            Favorito.objects.count()),
            ("✨ Destaques",            DestaqueAnuncio.objects.count()),
        ]
        self.stdout.write(self.style.HTTP_INFO("\nResumo da base de dados:"))
        for label, count in linhas:
            self.stdout.write(f"  {label:<25} {count}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("  Senha de todos os utilizadores: password123"))