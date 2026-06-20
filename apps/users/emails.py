"""
apps/users/emails.py

Envio de email de confirmação de conta.
Usa django.core.signing para gerar tokens seguros — sem modelo extra.

Configuração necessária em settings.py:
    EMAIL_BACKEND   — ex: 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST      — ex: 'smtp.gmail.com'
    EMAIL_PORT      — ex: 587
    EMAIL_USE_TLS   — True
    EMAIL_HOST_USER — remetente
    EMAIL_HOST_PASSWORD
    DEFAULT_FROM_EMAIL — ex: 'Zonal <no-reply@zonal.co.mz>'
    FRONTEND_URL    — ex: 'https://zonal.co.mz'  (sem / no fim)

Para desenvolvimento, usar:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
"""

import logging
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

# Namespace do token — evita colisões com outros tokens da app
_SALT = 'zonal-email-confirmacao'
# Validade do link: 24 horas
_MAX_AGE = 60 * 60 * 24


def _gerar_token(user) -> str:
    """Gera token HMAC assinado com o email e pk do utilizador."""
    return signing.dumps({'pk': user.pk, 'email': user.email}, salt=_SALT)


def _verificar_token(token: str) -> dict | None:
    """
    Valida e devolve o payload do token.
    Devolve None se inválido ou expirado.
    """
    try:
        return signing.loads(token, salt=_SALT, max_age=_MAX_AGE)
    except signing.SignatureExpired:
        logger.warning("Token de confirmação expirado")
        return None
    except signing.BadSignature:
        logger.warning("Token de confirmação inválido")
        return None


def enviar_email_confirmacao(user, request=None) -> bool:
    """
    Envia email de confirmação ao utilizador recém-registado.
    Devolve True se enviado, False em caso de erro.
    """
    token = _gerar_token(user)
    base_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')

    # Construir URL a partir do request se FRONTEND_URL não estiver definido
    if not base_url and request:
        base_url = request.build_absolute_uri('/').rstrip('/')

    link = f"{base_url}/auth/verificar-email/{token}/"

    contexto = {
        'user': user,
        'link': link,
        'validade_horas': _MAX_AGE // 3600,
    }

    try:
        # Tenta usar template HTML; se não existir, usa texto simples
        try:
            html_body = render_to_string('users/confirmacao.html', contexto)
            text_body = strip_tags(html_body)
        except Exception:
            text_body = (
                f"Olá {user.username},\n\n"
                f"Confirme a sua conta Zonal através do link abaixo:\n\n"
                f"{link}\n\n"
                f"O link é válido por {_MAX_AGE // 3600} horas.\n\n"
                f"Se não criou esta conta, ignore este email.\n\n"
                f"- Equipa Zonal"
            )
            html_body = None

        send_mail(
            subject='Confirme a sua conta Zonal',
            message=text_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@zonal.co.mz'),
            recipient_list=[user.email],
            html_message=html_body,
            fail_silently=False,
        )
        logger.info("Email de confirmação enviado para %s", user.email)
        return True

    except Exception as e:
        logger.error("Erro ao enviar email de confirmação para %s: %s", user.email, e)
        return False


def enviar_email_boas_vindas(user) -> tuple[bool, str | None]:
    """
    Envia email de boas-vindas a utilizadores que se registaram via Google.
    Não contém link de confirmação — o email já é verificado pelo Google.
    Devolve (True, None) se enviado, (False, motivo) em caso de erro.
    """
    contexto = {
            'user': user,
            'FRONTEND_URL': getattr(settings, 'FRONTEND_URL', 'https://www.zonal.co.mz'),
        }

    try:
        try:
            html_body = render_to_string('users/boas_vindas.html', contexto)
            text_body = strip_tags(html_body)
        except Exception as tmpl_err:
            logger.warning("Template 'users/boas_vindas.html' não encontrado (%s). A usar texto simples.", tmpl_err)
            text_body = (
                f"Olá {user.first_name or user.username}!\n\n"
                f"Bem-vindo ao Zonal — o mercado de Moçambique.\n\n"
                f"A sua conta foi criada com sucesso através do Google. "
                f"Já pode começar a publicar e a responder a anúncios.\n\n"
                f"Aceda em: {getattr(settings, 'FRONTEND_URL', 'https://www.zonal.co.mz')}\n\n"
                f"- Equipa Zonal"
            )
            html_body = None

        send_mail(
            subject='Bem-vindo ao Zonal!',
            message=text_body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@zonal.co.mz'),
            recipient_list=[user.email],
            html_message=html_body,
            fail_silently=False,
        )
        logger.info("Email de boas-vindas enviado para %s", user.email)
        return True, None

    except Exception as e:
        motivo = str(e)
        logger.error("Erro ao enviar email de boas-vindas para %s: %s", user.email, motivo)
        return False, motivo


def verificar_token_email(token: str):
    """
    Valida o token e devolve o User correspondente, ou None se inválido.
    Não modifica o utilizador — isso é responsabilidade da view.
    """
    from apps.users.models import User

    payload = _verificar_token(token)
    if not payload:
        return None, 'link_invalido'

    try:
        user = User.objects.get(pk=payload['pk'], email=payload['email'])
    except User.DoesNotExist:
        return None, 'utilizador_nao_encontrado'

    if user.email_verificado:
        return user, 'ja_verificado'

    return user, 'ok'