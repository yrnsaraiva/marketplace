from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.users.models import User
from apps.anuncios.models import *


# ---------------------------------------------------------------------------
# 1. PLANO DE PUBLICAÇÃO
# ---------------------------------------------------------------------------

class PlanoPublicacao(models.Model):
    TIPO_CHOICES = [
        ('avulso', 'Por Anúncio'),
        ('subscricao', 'Subscrição'),
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    preco = models.DecimalField(max_digits=12, decimal_places=2, help_text='Preço em Meticais (MZN)')
    max_anuncios = models.PositiveIntegerField(null=True, blank=True, help_text='Deixar em branco para ilimitado')
    duracao_anuncio_dias = models.PositiveIntegerField(default=30)
    duracao_subscricao_dias = models.PositiveIntegerField(default=30)
    max_imagens = models.PositiveIntegerField(default=6)
    dias_destaque_incluidos = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
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
        return self.preco == Decimal('0')

    @property
    def ilimitado(self):
        return self.max_anuncios is None

    @property
    def preco_por_anuncio(self):
        if self.tipo == 'avulso' or self.ilimitado or not self.max_anuncios:
            return self.preco
        return (self.preco / Decimal(self.max_anuncios)).quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# 2. SUBSCRIÇÃO DO UTILIZADOR
# ---------------------------------------------------------------------------

class SubscricaoUtilizador(models.Model):
    ESTADO_CHOICES = [
        ('pendente', 'Pendente de Pagamento'),
        ('activa', 'Activa'),
        ('expirada', 'Expirada'),
        ('cancelada', 'Cancelada'),
    ]

    utilizador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscricoes')
    plano = models.ForeignKey(PlanoPublicacao, on_delete=models.PROTECT, related_name='subscricoes')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendente')
    creditos_totais = models.PositiveIntegerField(null=True, blank=True)
    creditos_usados = models.PositiveIntegerField(default=0)
    inicio_em = models.DateTimeField(null=True, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)
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

    @property
    def ilimitado(self):
        return self.creditos_totais is None

    @property
    def creditos_disponiveis(self):
        if self.ilimitado:
            return None
        return max(0, self.creditos_totais - self.creditos_usados)

    @property
    def expirada(self):
        if not self.expira_em:
            return False
        return timezone.now() > self.expira_em

    @property
    def valida(self):
        return self.estado == 'activa' and not self.expirada

    def activar(self):
        self.estado = 'activa'
        self.inicio_em = timezone.now()
        self.expira_em = self.inicio_em + timedelta(days=self.plano.duracao_subscricao_dias)
        self.save(update_fields=['estado', 'inicio_em', 'expira_em', 'actualizado_em'])

    def tem_credito(self):
        if not self.valida:
            return False
        if self.ilimitado:
            return True
        return self.creditos_disponiveis > 0

    def consumir_credito(self):
        """
        FIX: usa select_for_update() para evitar race condition.
        Dois requests simultâneos não conseguem ambos consumir o mesmo crédito.
        Deve ser chamado dentro de uma transacção atómica.
        """
        # Re-ler com lock ao nível de linha
        sub = (
            SubscricaoUtilizador.objects
            .select_for_update()
            .get(pk=self.pk)
        )
        if not sub.tem_credito():
            raise ValueError('Subscrição sem créditos disponíveis ou inválida.')
        if not sub.ilimitado:
            sub.creditos_usados += 1
            sub.save(update_fields=['creditos_usados', 'actualizado_em'])
            # Sincronizar o objecto em memória
            self.creditos_usados = sub.creditos_usados
        return sub.plano.duracao_anuncio_dias


# ---------------------------------------------------------------------------
# 3. PAGAMENTO
# ---------------------------------------------------------------------------

class Pagamento(models.Model):
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

    subscricao = models.ForeignKey(SubscricaoUtilizador, on_delete=models.PROTECT, related_name='pagamentos')
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendente')
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    referencia_externa = models.CharField(max_length=255, blank=True)
    telefone_pagamento = models.CharField(max_length=20, blank=True)
    confirmado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pagamentos_confirmados'
    )
    confirmado_em = models.DateTimeField(null=True, blank=True)
    resposta_gateway = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        ordering = ['-criado_em']

    def __str__(self):
        return f'Pagamento #{self.pk} - {self.subscricao.utilizador.username} - {self.valor} MZN ({self.estado})'

    @transaction.atomic
    def confirmar(self, confirmado_por=None):
        """
        FIX: wrapped em @transaction.atomic.
        Se subscricao.activar() falha, o pagamento NÃO fica marcado como confirmado.
        """
        self.estado = 'confirmado'
        self.confirmado_por = confirmado_por
        self.confirmado_em = timezone.now()
        self.save(update_fields=['estado', 'confirmado_por', 'confirmado_em', 'actualizado_em'])
        self.subscricao.activar()


# ---------------------------------------------------------------------------
# 4. DESTAQUE DE ANÚNCIO
# ---------------------------------------------------------------------------

class DestaqueAnuncio(models.Model):
    anuncio = models.ForeignKey('anuncios.Anuncio', on_delete=models.CASCADE, related_name='destaques')
    subscricao = models.ForeignKey(
        SubscricaoUtilizador, on_delete=models.PROTECT, related_name='destaques'
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