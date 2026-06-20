from django.db import models
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User

# FIX: imports explícitos em vez de wildcard (from ... import *)
from apps.categorias.models import *
from apps.pagamentos.models import *


class Anuncio(models.Model):
    CONDICAO_CHOICES = [
        ('novo', 'Novo'),
        ('usado', 'Usado'),
        ('recondicionado', 'Recondicionado'),
    ]
    ESTADO_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('pendente_pagamento', 'Pendente de Pagamento'),
        ('activo', 'Activo'),
        ('pausado', 'Pausado'),
        ('vendido', 'Vendido'),
        ('expirado', 'Expirado'),
        ('eliminado', 'Eliminado'),
        ('rejeitado', 'Rejeitado'),
    ]

    utilizador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='anuncios')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='anuncios')
    subscricao = models.ForeignKey(
        SubscricaoUtilizador, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='anuncios_publicados',
    )
    titulo = models.CharField(max_length=100)
    descricao = models.TextField(max_length=2000)
    preco = models.DecimalField(max_digits=12, decimal_places=2)
    preco_negociavel = models.BooleanField(default=False)
    condicao = models.CharField(max_length=20, choices=CONDICAO_CHOICES, default='novo')
    provincia = models.CharField(max_length=50)
    cidade = models.CharField(max_length=50)
    bairro = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='pendente_pagamento')
    motivo_rejeicao = models.TextField(blank=True)
    visualizacoes = models.PositiveIntegerField(default=0)
    contactos_recebidos = models.PositiveIntegerField(default=0)
    auto_renovar = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    actualizado_em = models.DateTimeField(auto_now=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Anúncio'
        verbose_name_plural = 'Anúncios'
        ordering = ['-publicado_em']

    def __str__(self):
        return self.titulo

    def registar_visualizacao(self, utilizador=None):
        """
        FIX: usa F() expression para evitar race condition.
        Dois requests simultâneos já não lêem o mesmo valor e ambos gravam +1 correcto.
        FIX: não conta visualizações do próprio dono.
        """
        if utilizador and utilizador.is_authenticated and utilizador.pk == self.utilizador_id:
            return
        Anuncio.objects.filter(pk=self.pk).update(visualizacoes=F('visualizacoes') + 1)

    def registar_contacto(self):
        """FIX: também usa F() expression."""
        Anuncio.objects.filter(pk=self.pk, estado='activo').update(
            contactos_recebidos=F('contactos_recebidos') + 1
        )

    def activar(self, duracao_dias=30):
        self.estado = 'activo'
        self.publicado_em = timezone.now()
        self.expira_em = self.publicado_em + timedelta(days=duracao_dias)
        self.save(update_fields=['estado', 'publicado_em', 'expira_em', 'subscricao_id', 'actualizado_em'])

    @property
    def max_imagens_permitidas(self):
        if self.subscricao and self.subscricao.plano:
            return self.subscricao.plano.max_imagens
        return 6

    @property
    def destacado(self):
        return self.destaques.filter(activo=True, fim_em__gt=timezone.now()).exists()


class ImagemAnuncio(models.Model):
    anuncio = models.ForeignKey(Anuncio, on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField(upload_to='anuncios/%Y/%m/')
    ordem = models.PositiveIntegerField(default=0)
    principal = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagem do anúncio'
        verbose_name_plural = 'Imagens do anúncio'
        ordering = ['ordem']

    def save(self, *args, **kwargs):
        if self.principal:
            ImagemAnuncio.objects.filter(anuncio=self.anuncio, principal=True).update(principal=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Imagem {self.ordem} — {self.anuncio.titulo}'


class AtributoAnuncio(models.Model):
    anuncio = models.ForeignKey(Anuncio, on_delete=models.CASCADE, related_name='atributos')
    atributo = models.ForeignKey(AtributoCategoria, on_delete=models.CASCADE)
    valor = models.CharField(max_length=255)

    class Meta:
        verbose_name = 'Atributo do anúncio'
        unique_together = ['anuncio', 'atributo']

    def __str__(self):
        return f'{self.atributo.nome}: {self.valor}'


class Favorito(models.Model):
    utilizador = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favoritos')
    anuncio = models.ForeignKey(Anuncio, on_delete=models.CASCADE, related_name='favoritos')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favorito'
        unique_together = ['utilizador', 'anuncio']

    def __str__(self):
        return f'{self.utilizador.username} — {self.anuncio.titulo}'