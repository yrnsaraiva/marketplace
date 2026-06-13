"""
apps/users/views.py — versão com allauth Google
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

from .forms import RegistoCaptchaForm
from .models import User
from .serializers import AlterarPasswordSerializer, PerfilSerializer, RegistoSerializer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Signal: guardar tokens JWT na sessão após qualquer login (local ou Google)
# Isto garante que o JS tem sempre tokens disponíveis após login.
# ─────────────────────────────────────────────────────────────────────────────
@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """
    Disparado após qualquer login (email/password OU Google).
    Gera tokens JWT e guarda-os na sessão para o JS os ler.
    """
    try:
        refresh = RefreshToken.for_user(user)
        request.session['jwt_access']  = str(refresh.access_token)
        request.session['jwt_refresh'] = str(refresh)
    except Exception as e:
        logger.warning(f'Não foi possível gerar JWT após login: {e}')


# ---------------------------------------------------------------------------
# API — Autenticação
# ---------------------------------------------------------------------------
class RegistoView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegistoSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'mensagem': 'Conta criada com sucesso.',
            'user': PerfilSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email    = request.data.get('email', '').strip().lower()
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
            return Response({'erro': 'Password actual incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)

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
# Frontend — vistas de template
# ---------------------------------------------------------------------------
def login_template_view(request):
    return render(request, 'users/login.html')


def signup_template_view(request):
    """
    Registo local com captcha. O login Google é tratado inteiramente
    pelo allauth em /accounts/google/login/.
    """
    if request.method == 'POST':
        form = RegistoCaptchaForm(request.POST)

        if form.is_valid():
            data = {
                'username':  form.cleaned_data['username'],
                'email':     form.cleaned_data['email'],
                'password':  form.cleaned_data['password'],
                'password2': form.cleaned_data['password2'],
                'telefone':  form.cleaned_data.get('telefone', ''),
            }
            serializer = RegistoSerializer(data=data)

            if serializer.is_valid():
                user = serializer.save()
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                # O signal on_user_logged_in já guarda os tokens na sessão
                return redirect(request.GET.get('next', '/'))
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
