from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    PAPEL_CHOICES = [
        ('utilizador', 'Utilizador'),
        ('moderador', 'Moderador'),
        ('admin', 'Admin'),
    ]

    telefone = models.CharField(max_length=20, blank=True)
    foto_perfil = models.ImageField(upload_to='avatars/', blank=True, null=True)
    telefone_verificado = models.BooleanField(default=False)
    email_verificado = models.BooleanField(default=False)
    provincia = models.CharField(max_length=50, blank=True)
    cidade = models.CharField(max_length=50, blank=True)
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default='utilizador')
    bloqueado = models.BooleanField(default=False)
    motivo_bloqueio = models.TextField(blank=True)
    total_anuncios = models.PositiveIntegerField(default=0)
    avaliacao_media = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    ultimo_acesso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Utilizador'
        verbose_name_plural = 'Utilizadores'

    def __str__(self):
        return self.email