"""
apps/users/views.py
"""
import logging

from django.contrib.auth import authenticate, login
from django.dispatch import receiver
from django.shortcuts import render, redirect
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from allauth.socialaccount.signals import social_account_added, pre_social_login
from allauth.account.signals import user_logged_in

from .emails import enviar_email_confirmacao, enviar_email_boas_vindas, verificar_token_email
from .forms import RegistoCaptchaForm
from .models import User
from .serializers import AlterarPasswordSerializer, PerfilSerializer, RegistoSerializer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Signal: guardar tokens JWT na sessão após qualquer login
# ─────────────────────────────────────────────────────────────────────────────
@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    try:
        refresh = RefreshToken.for_user(user)
        request.session['jwt_access']  = str(refresh.access_token)
        request.session['jwt_refresh'] = str(refresh)
    except Exception as e:
        logger.warning('Não foi possível gerar JWT após login: %s', e)


@receiver(social_account_added)
def on_social_account_added(sender, request, sociallogin, **kwargs):
    """
    Disparado quando um utilizador se regista pela primeira vez via Google.
    — Marca email_verificado=True (o Google já verificou o email)
    — Envia email de boas-vindas
    """
    user = sociallogin.user

    if not user.email_verificado:
        user.email_verificado = True
        user.save(update_fields=['email_verificado'])
        logger.info("email_verificado=True definido para utilizador social #%s (%s)", user.pk, user.email)

    enviar_email_boas_vindas(user)


# ---------------------------------------------------------------------------
# API — Registo
# ---------------------------------------------------------------------------
class RegistoView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegistoSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        email_enviado, email_erro = enviar_email_confirmacao(user, request=request)

        refresh = RefreshToken.for_user(user)
        resposta = {
            'mensagem': 'Conta criada com sucesso. Verifique o seu email para activar a conta.',
            'email_confirmacao_enviado': email_enviado,
            'user': PerfilSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }

        from django.conf import settings as django_settings
        if not email_enviado and django_settings.DEBUG and email_erro:
            resposta['email_erro_debug'] = email_erro

        return Response(resposta, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# API — Verificação de email
# ---------------------------------------------------------------------------
class VerificarEmailView(APIView):
    """
    GET /api/v1/auth/verificar-email/<token>/
    Valida o token e marca email_verificado=True.
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        user, estado = verificar_token_email(token)

        if estado == 'ja_verificado':
            return Response({'mensagem': 'Email já verificado anteriormente.'})

        if estado != 'ok' or not user:
            return Response(
                {'erro': 'Link inválido ou expirado. Solicite um novo email de confirmação.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.email_verificado = True
        user.save(update_fields=['email_verificado'])
        logger.info("Email verificado para utilizador #%s (%s)", user.pk, user.email)

        return Response({'mensagem': 'Email confirmado com sucesso. Pode agora iniciar sessão.'})


class ReenviarConfirmacaoView(APIView):
    """
    POST /api/v1/auth/reenviar-confirmacao/
    Reenvia o email de confirmação para o utilizador autenticado.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.email_verificado:
            return Response(
                {'mensagem': 'O seu email já está verificado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enviado, erro = enviar_email_confirmacao(user, request=request)
        if enviado:
            return Response({'mensagem': 'Email de confirmação reenviado.'})
        return Response(
            {'erro': f'Erro ao enviar email: {erro}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ---------------------------------------------------------------------------
# API — Login
# ---------------------------------------------------------------------------
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')

        if not email or not password:
            return Response(
                {'erro': 'Email e password são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_obj = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({'erro': 'Credenciais inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

        user = authenticate(request, username=user_obj.username, password=password)
        if not user:
            return Response({'erro': 'Credenciais inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

        if user.bloqueado:
            return Response(
                {'erro': f'Conta bloqueada. Motivo: {user.motivo_bloqueio}'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.ultimo_acesso = timezone.now()
        user.save(update_fields=['ultimo_acesso'])

        refresh = RefreshToken.for_user(user)
        return Response({
            'user': PerfilSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        })


# ---------------------------------------------------------------------------
# API — Logout / Perfil / Password
# ---------------------------------------------------------------------------
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            pass
        return Response({'mensagem': 'Sessão terminada.'})


class PerfilView(generics.RetrieveUpdateAPIView):
    serializer_class = PerfilSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AlterarPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AlterarPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['password_actual']):
            return Response(
                {'erro': 'Password actual incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['password_nova'])
        user.save()

        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            pass

        return Response({'mensagem': 'Password alterada com sucesso. Faça login novamente.'})


# ---------------------------------------------------------------------------
# Frontend — templates
# ---------------------------------------------------------------------------
def login_template_view(request):
    return render(request, 'users/login.html')


def signup_template_view(request):
    if request.method == 'POST':
        form = RegistoCaptchaForm(request.POST)

        if form.is_valid():
            data = {
                'username':        form.cleaned_data['username'],
                'email':           form.cleaned_data['email'],
                'password':        form.cleaned_data['password'],
                'password2':       form.cleaned_data['password2'],
                'telefone':        form.cleaned_data.get('telefone', ''),
                'data_nascimento': form.cleaned_data.get('data_nascimento'),
            }
            serializer = RegistoSerializer(data=data)

            if serializer.is_valid():
                user = serializer.save()
                enviar_email_confirmacao(user, request=request)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect(request.GET.get('next', 'perfil'))
            else:
                serializer_errors = {
                    k: v[0] if isinstance(v, list) else v
                    for k, v in serializer.errors.items()
                }
                return render(request, 'users/signup.html', {
                    'form': form,
                    'serializer_errors': serializer_errors,
                })

        return render(request, 'users/signup.html', {'form': form})

    return render(request, 'users/signup.html', {'form': RegistoCaptchaForm()})


def verificar_email_view(request, token):
    """
    Vista de template para verificação de email.
    O utilizador chega aqui pelo link no email.
    Usa 'users/email_verificado.html' (página de resultado),
    distinto de 'users/confirmacao.html' (corpo do email enviado).
    """
    user, estado = verificar_token_email(token)

    if estado == 'ja_verificado':
        return render(request, 'users/email_verificado.html', {
            'sucesso': True,
            'mensagem': 'O seu email já estava verificado.',
        })

    if estado != 'ok' or not user:
        return render(request, 'users/email_verificado.html', {
            'sucesso': False,
            'mensagem': 'Link inválido ou expirado. Solicite um novo email de confirmação.',
        })

    user.email_verificado = True
    user.save(update_fields=['email_verificado'])
    logger.info("Email verificado (template) para utilizador #%s", user.pk)

    return render(request, 'users/email_verificado.html', {
        'sucesso': True,
        'mensagem': 'Email confirmado com sucesso! Já pode usar a sua conta.',
    })