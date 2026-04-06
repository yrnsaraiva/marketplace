from django.db import models


class Categoria(models.Model):
    pai = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='subcategorias'
    )
    nome = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    icone_url = models.CharField(max_length=255, blank=True)
    ordem = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)
    nivel = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = ['ordem', 'nome']

    def save(self, *args, **kwargs):
        if self.pai:
            self.nivel = self.pai.nivel + 1
        else:
            self.nivel = 0
        super().save(*args, **kwargs)

    def __str__(self):
        if self.pai:
            return f'{self.pai.nome} > {self.nome}'
        return self.nome


class AtributoCategoria(models.Model):
    TIPO_CHOICES = [
        ('texto', 'Texto'),
        ('numero', 'Número'),
        ('lista', 'Lista de opções'),
        ('booleano', 'Sim / Não'),
    ]

    categoria = models.ForeignKey(
        Categoria, on_delete=models.CASCADE, related_name='atributos'
    )
    nome = models.CharField(max_length=100)
    chave = models.SlugField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='texto')
    opcoes = models.JSONField(
        null=True, blank=True,
        help_text='Para tipo lista: ["Opção 1", "Opção 2"]'
    )
    obrigatorio = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Atributo de categoria'
        verbose_name_plural = 'Atributos de categoria'
        unique_together = ['categoria', 'chave']

    def __str__(self):
        return f'{self.categoria.nome} — {self.nome}'