"""
tasks.py — Tarefas Celery para gestão automática de subscrições e anúncios.

Adicionar ao settings.py:

    CELERY_BEAT_SCHEDULE = {
        'expirar-subscricoes': {
            'task': 'apps.pagamentos.tasks.expirar_subscricoes',
            'schedule': crontab(hour=0, minute=0),  # meia-noite todos os dias
        },
        'expirar-anuncios': {
            'task': 'apps.pagamentos.tasks.expirar_anuncios',
            'schedule': crontab(hour=1, minute=0),  # 1h da manhã
        },
        'expirar-destaques': {
            'task': 'apps.pagamentos.tasks.expirar_destaques',
            'schedule': crontab(hour=2, minute=0),
        },
    }
"""

from celery import shared_task
from django.utils import timezone


@shared_task
def expirar_subscricoes():
    """Marca como expiradas todas as subscrições cuja validade passou."""
    from apps.pagamentos.models import SubscricaoUtilizador

    expiradas = SubscricaoUtilizador.objects.filter(
        estado='activa',
        expira_em__lt=timezone.now(),
    )
    total = expiradas.update(estado='expirada')
    return f'{total} subscrição(ões) expirada(s).'


@shared_task
def expirar_anuncios():
    """Marca como expirados todos os anúncios cuja data de expiração passou."""
    from apps.anuncios.models import Anuncio

    expirados = Anuncio.objects.filter(
        estado='activo',
        expira_em__lt=timezone.now(),
    )
    total = expirados.update(estado='expirado')
    return f'{total} anúncio(s) expirado(s).'


@shared_task
def expirar_destaques():
    """Desactiva destaques cuja data de fim passou."""
    from apps.pagamentos.models import DestaqueAnuncio

    expirados = DestaqueAnuncio.objects.filter(
        activo=True,
        fim_em__lt=timezone.now(),
    )
    total = expirados.update(activo=False)
    return f'{total} destaque(s) desactivado(s).'