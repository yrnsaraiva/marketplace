from django.db import models


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

    def __str__(self):
        return self.nome


class DestaqueAnuncio(models.Model):
    from apps.anuncios.models import Anuncio

    anuncio = models.ForeignKey(Anuncio, on_delete=models.CASCADE, related_name='destaques')
    plano = models.ForeignKey(PlanoDestaque, on_delete=models.PROTECT)
    inicio_em = models.DateTimeField(auto_now_add=True)
    fim_em = models.DateTimeField()
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Destaque de anúncio'

    def __str__(self):
        return f'{self.anuncio.titulo} — {self.plano.nome}'