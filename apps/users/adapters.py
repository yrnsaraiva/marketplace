"""
apps/users/adapters.py

Adaptadores que ligam o django-allauth ao modelo User customizado do projecto.

AccountAdapter   — controla criação de contas locais (email/password)
SocialAccountAdapter — controla criação de contas via Google (e outros providers)
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """
    Adaptador para contas locais.
    Preenche campos extra do modelo User (telefone, papel) se vierem no request.
    """

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        # Campos extra que o nosso modelo tem mas o allauth não conhece
        data = form.cleaned_data
        user.telefone = data.get('telefone', '')
        if commit:
            user.save()
        return user

    def get_login_redirect_url(self, request):
        return settings.LOGIN_REDIRECT_URL


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adaptador para contas sociais (Google, etc.).

    Quando o utilizador faz login com Google:
    1. Se já existe um User com esse email → liga a conta Google ao User existente
    2. Se não existe → cria um User novo preenchendo os campos do nosso modelo
    """

    def pre_social_login(self, request, sociallogin):
        """
        Ligar conta Google a um User existente com o mesmo email.
        Evita criar duplicados quando o utilizador já tinha conta local.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if sociallogin.is_existing:
            return

        if not sociallogin.email_addresses:
            return

        email = sociallogin.email_addresses[0].email.lower()
        try:
            user = User.objects.get(email__iexact=email)
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            pass  # utilizador novo — allauth cria automaticamente

    def populate_user(self, request, sociallogin, data):
        """
        Preencher os campos do nosso User com os dados do Google.
        'data' contém: first_name, last_name, email, username, name
        """
        user = super().populate_user(request, sociallogin, data)

        # Nome completo do Google
        if not user.first_name and data.get('name'):
            partes = data['name'].split(' ', 1)
            user.first_name = partes[0]
            user.last_name  = partes[1] if len(partes) > 1 else ''

        # papel padrão
        if hasattr(user, 'papel'):
            user.papel = 'utilizador'

        return user

    def get_connect_redirect_url(self, request, socialaccount):
        # Se o utilizador não tem data de nascimento, redirecionar para o perfil
        # para preencher a informação em falta (validação de idade mínima)
        user = socialaccount.user
        if not getattr(user, 'data_nascimento', None):
            return '/dashboard/perfil/?completar=1'
        return settings.LOGIN_REDIRECT_URL