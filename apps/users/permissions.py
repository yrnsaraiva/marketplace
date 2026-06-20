"""
apps/users/permissions.py

Permissões reutilizáveis para restringir acesso a utilizadores
com conta activa (email verificado + idade mínima confirmada).

─── API (DRF) ────────────────────────────────────────────────
    from apps.users.permissions import ContaActivaPermission

    class PublicarAnuncioView(generics.CreateAPIView):
        permission_classes = [IsAuthenticated, ContaActivaPermission]

─── Template views ───────────────────────────────────────────
    from apps.users.permissions import conta_activa_required

    @login_required
    @conta_activa_required
    def publicar_anuncio_view(request):
        ...
"""

from datetime import date
from functools import wraps

from django.shortcuts import redirect
from django.contrib import messages
from rest_framework.permissions import BasePermission

IDADE_MINIMA = 18


def _calcular_idade(data_nascimento) -> int | None:
    if not data_nascimento:
        return None
    hoje = date.today()
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


def _validar_conta(user) -> tuple[bool, str]:
    """
    Verifica se o utilizador pode publicar.
    Devolve (True, '') ou (False, motivo).
    """
    if not user.email_verificado:
        return False, 'email_nao_verificado'

    idade = _calcular_idade(getattr(user, 'data_nascimento', None))
    if idade is None:
        return False, 'idade_nao_confirmada'

    if idade < IDADE_MINIMA:
        return False, 'menor_de_idade'

    return True, ''


# ─────────────────────────────────────────────────────────────
# DRF — permission class
# ─────────────────────────────────────────────────────────────

_MENSAGENS_API = {
    'email_nao_verificado': (
        'A sua conta ainda não está verificada. '
        'Confirme o seu email antes de publicar anúncios.'
    ),
    'idade_nao_confirmada': (
        'É necessário confirmar a sua data de nascimento no perfil '
        'antes de publicar anúncios.'
    ),
    'menor_de_idade': (
        f'É necessário ter pelo menos {IDADE_MINIMA} anos para publicar anúncios.'
    ),
}


class ContaActivaPermission(BasePermission):
    """
    Permite acesso apenas a utilizadores com:
    - email verificado
    - data de nascimento preenchida e com pelo menos 18 anos
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        permitido, motivo = _validar_conta(request.user)
        if not permitido:
            self.message = _MENSAGENS_API.get(motivo, 'Conta não autorizada a publicar.')
        return permitido


# ─────────────────────────────────────────────────────────────
# Template views — decorator
# ─────────────────────────────────────────────────────────────

_MENSAGENS_TEMPLATE = {
    'email_nao_verificado': (
        'Confirme o seu email antes de publicar anúncios. '
        'Verifique a sua caixa de entrada.'
    ),
    'idade_nao_confirmada': (
        'Preencha a sua data de nascimento no perfil antes de publicar anúncios.'
    ),
    'menor_de_idade': (
        f'É necessário ter pelo menos {IDADE_MINIMA} anos para publicar anúncios.'
    ),
}


def conta_activa_required(view_func):
    """
    Decorator para views de template.
    Redireciona para o perfil com mensagem de erro se a conta não estiver activa.

    Uso (após @login_required):
        @login_required
        @conta_activa_required
        def publicar_anuncio_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        permitido, motivo = _validar_conta(request.user)
        if not permitido:
            mensagem = _MENSAGENS_TEMPLATE.get(motivo, 'Conta não autorizada a publicar.')
            messages.error(request, mensagem)
            # Redirecionar para perfil para o utilizador resolver o problema
            return redirect('/dashboard/perfil/')
        return view_func(request, *args, **kwargs)
    return wrapper
