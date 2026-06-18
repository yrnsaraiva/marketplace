from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.users.models import *
from apps.anuncios.models import *


# ---------------------------------------------------------------------------
# 1. PLANO DE PUBLICAÇÃO
# ---------------------------------------------------------------------------

class PlanoPublicacao(models.Model):
    """
    Define os planos disponíveis para publicar anúncios.

    Dois tipos:
      - 'avulso'      → o utilizador paga por cada anúncio individualmente
      - 'subscricao'  → compra um pacote com N créditos válidos por X dias
    """

    TIPO_CHOICES = [
        ('avulso', 'Por Anúncio'),
        ('subscricao', 'Subscrição'),
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    preco = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Preço em Meticais (MZN)'
    )

    # Quantos anúncios o plano permite publicar.
    # None = ilimitado (só válido para subscrições)
    max_anuncios = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Deixar em branco para ilimitado'
    )

    # Quantos dias o anúncio fica publicado depois de activado
    duracao_anuncio_dias = models.PositiveIntegerField(
        default=30,
        help_text='Duração de cada anúncio em dias'
    )

    # Quantos dias a subscrição é válida (ignorado para avulso)
    duracao_subscricao_dias = models.PositiveIntegerField(
        default=30,
        help_text='Validade da subscrição em dias'
    )

    max_imagens = models.PositiveIntegerField(
        default=6,
        help_text='Número máximo de imagens por anúncio'
    )

    # Dias de destaque incluídos por anúncio (0 = sem destaque)
    dias_destaque_incluidos = models.PositiveIntegerField(
        default=0,
        help_text='Dias de destaque automático incluídos em cada anúncio'
    )

    activo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(
        default=0,
        help_text='Ordem de exibição na página de planos'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plano de publicação'
        verbose_name_plural = 'Planos de publicação'
        ordering = ['ordem', 'preco']

    def __str__(self):
        return f'{self.nome} — {self.preco} MZN'

    @property
    def gratuito(self):
        return self.preco == 0

    @property
    def ilimitado(self):
        return self.max_anuncios is None

    @property
    def preco_por_anuncio(self):
        """Preço efectivo por anúncio (útil para mostrar na UI)."""
        if self.tipo == 'avulso' or self.ilimitado or not self.max_anuncios:
            return self.preco
        return (self.preco / Decimal(self.max_anuncios)).quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# 2. SUBSCRIÇÃO DO UTILIZADOR
# ---------------------------------------------------------------------------

class SubscricaoUtilizador(models.Model):
    """
    Regista a compra de um plano por um utilizador.

    Para planos 'avulso': cada compra cria uma subscrição com 1 crédito.
    Para planos 'subscricao': cria uma subscrição com N créditos válidos
    até 'expira_em'.
    """

    ESTADO_CHOICES = [
        ('pendente', 'Pendente de Pagamento'),
        ('activa', 'Activa'),
        ('expirada', 'Expirada'),
        ('cancelada', 'Cancelada'),
    ]

    utilizador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='subscricoes'
    )
    plano = models.ForeignKey(
        PlanoPublicacao,
        on_delete=models.PROTECT,
        related_name='subscricoes'
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='pendente'
    )

    # Créditos disponíveis. None = ilimitado
    creditos_totais = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Total de anúncios incluídos. Nulo = ilimitado.'
    )
    creditos_usados = models.PositiveIntegerField(default=0)

    inicio_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    # Preço pago no momento da compra (snapshot histórico)
    preco_pago = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Subscrição'
        verbose_name_plural = 'Subscrições'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['utilizador', 'estado', 'expira_em']),
        ]

    def __str__(self):
        return f'{self.utilizador.username} — {self.plano.nome} ({self.estado})'

    # ------------------------------------------------------------------
    # Propriedades de conveniência
    # ------------------------------------------------------------------

    @property
    def ilimitado(self):
        return self.creditos_totais is None

    @property
    def creditos_disponiveis(self):
        if self.ilimitado:
            return None  # sem limite
        return max(0, self.creditos_totais - self.creditos_usados)

    @property
    def expirada(self):
        if not self.expira_em:
            return False
        return timezone.now() > self.expira_em

    @property
    def valida(self):
        """True se a subscrição está activa e não expirou."""
        return self.estado == 'activa' and not self.expirada

    # ------------------------------------------------------------------
    # Métodos de negócio
    # ------------------------------------------------------------------

    def activar(self):
        """Activa a subscrição após confirmação de pagamento."""
        self.estado = 'activa'
        self.inicio_em = timezone.now()
        self.expira_em = self.inicio_em + timedelta(
            days=self.plano.duracao_subscricao_dias
        )
        self.save(update_fields=['estado', 'inicio_em', 'expira_em', 'actualizado_em'])

    def tem_credito(self):
        """Verifica se pode publicar mais um anúncio."""
        if not self.valida:
            return False
        if self.ilimitado:
            return True
        return self.creditos_disponiveis > 0

    def consumir_credito(self):
        """
        Desconta 1 crédito. Lança ValueError se não houver crédito disponível.
        Retorna o número de dias de duração do anúncio definido pelo plano.
        """
        if not self.tem_credito():
            raise ValueError(
                'Subscrição sem créditos disponíveis ou inválida.'
            )
        if not self.ilimitado:
            self.creditos_usados += 1
            self.save(update_fields=['creditos_usados', 'actualizado_em'])
        return self.plano.duracao_anuncio_dias


# ---------------------------------------------------------------------------
# 3. PAGAMENTO
# ---------------------------------------------------------------------------

class Pagamento(models.Model):
    """
    Regista cada transacção financeira associada a uma subscrição.
    Suporta confirmação manual (admin) e futura integração com M-Pesa/e-Mola.
    """

    METODO_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('emola', 'e-Mola'),
        ('transferencia', 'Transferência Bancária'),
        ('manual', 'Confirmação Manual'),
        ('gratuito', 'Gratuito'),
    ]

    ESTADO_CHOICES = [
        ('pendente', 'Pendente'),
        ('confirmado', 'Confirmado'),
        ('falhado', 'Falhado'),
        ('reembolsado', 'Reembolsado'),
    ]

    subscricao = models.ForeignKey(
        SubscricaoUtilizador,
        on_delete=models.PROTECT,
        related_name='pagamentos'
    )
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='pendente'
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)

    # Referência externa do gateway (ex: ID de transacção M-Pesa)
    referencia_externa = models.CharField(max_length=255, blank=True)

    # Número de telefone usado no pagamento mobile money
    telefone_pagamento = models.CharField(max_length=20, blank=True)

    # Quem confirmou manualmente (se aplicável)
    confirmado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pagamentos_confirmados'
    )
    confirmado_em = models.DateTimeField(null=True, blank=True)

    # Payload completo da resposta do gateway (para auditoria)
    resposta_gateway = models.JSONField(default=dict, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        ordering = ['-criado_em']

    def __str__(self):
        return (
            f'Pagamento #{self.pk} - {self.subscricao.utilizador.username} '
            f'- {self.valor} MZN ({self.estado})'
        )

    def confirmar(self, confirmado_por=None):
        """
        Confirma o pagamento e activa a subscrição associada.
        Pode ser chamado pelo admin ou pelo callback do gateway.
        """
        self.estado = 'confirmado'
        self.confirmado_por = confirmado_por
        self.confirmado_em = timezone.now()
        self.save(update_fields=[
            'estado', 'confirmado_por', 'confirmado_em', 'actualizado_em'
        ])
        self.subscricao.activar()


# ---------------------------------------------------------------------------
# 4. DESTAQUE DE ANÚNCIO
# ---------------------------------------------------------------------------

class DestaqueAnuncio(models.Model):
    """
    Activa o destaque de um anúncio com base nos dias incluídos
    no PlanoPublicacao da subscrição do utilizador.
    Não existe compra avulsa de destaque.
    """

    anuncio = models.ForeignKey(
        'anuncios.Anuncio',
        on_delete=models.CASCADE,
        related_name='destaques'
    )
    subscricao = models.ForeignKey(
        SubscricaoUtilizador,
        on_delete=models.PROTECT,
        related_name='destaques',
        help_text='Subscrição que originou este destaque'
    )
    inicio_em = models.DateTimeField(auto_now_add=True)
    fim_em = models.DateTimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Destaque de anúncio'
        verbose_name_plural = 'Destaques de anúncios'
        ordering = ['-inicio_em']
        indexes = [
            models.Index(fields=['activo', 'fim_em']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['anuncio'],
                condition=models.Q(activo=True),
                name='unique_active_destaque_per_anuncio'
            )
        ]

    @property
    def expirado(self):
        return timezone.now() > self.fim_em

    def __str__(self):
        return f'{self.anuncio} - destaque até {self.fim_em}'