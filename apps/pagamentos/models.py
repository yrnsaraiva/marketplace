from datetime import timedelta

from django.db import models
from django.utils import timezone


class PlanoDestaque(models.Model):
    TIPO_CHOICES = [
        ('destaque', 'Destaque'),
        ('patrocinado', 'Patrocinado'),
        ('urgente', 'Urgente'),
        ('topo_pagina', 'Topo da Página'),
    ]

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    duracao_dias = models.PositiveIntegerField(default=30)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    boost_visualizacoes = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Plano de destaque'
        verbose_name_plural = 'Planos de destaque'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class DestaqueAnuncio(models.Model):
    anuncio = models.ForeignKey(
        'anuncios.Anuncio',
        on_delete=models.CASCADE,
        related_name='destaques'
    )
    plano = models.ForeignKey(
        PlanoDestaque,
        on_delete=models.PROTECT
    )
    inicio_em = models.DateTimeField(auto_now_add=True)
    fim_em = models.DateTimeField(blank=True, null=True)
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

    def save(self, *args, **kwargs):
        # define automaticamente a data de fim com base no plano
        if not self.fim_em:
            self.fim_em = timezone.now() + timedelta(days=self.plano.duracao_dias)
        super().save(*args, **kwargs)

    @property
    def expirado(self):
        if not self.fim_em:
            return False
        return timezone.now() > self.fim_em

    def __str__(self):
        return f'{self.anuncio} — {self.plano.nome}'