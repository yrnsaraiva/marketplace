"""
apps/users/views.py

Contém as views de autenticação API e as views de template.
"""
import logging

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .forms import RegistoCaptchaForm
from .models import User
from .serializers import AlterarPasswordSerializer, PerfilSerializer, RegistoSerializer

logger = logging.getLogger(__name__)


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
            return Response(
                {'erro': 'Credenciais inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = authenticate(request, username=user_obj.username, password=password)
        if not user:
            return Response(
                {'erro': 'Credenciais inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

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
# Frontend — vistas de template
# ---------------------------------------------------------------------------
def login_template_view(request):
    return render(request, 'users/login.html')


def signup_template_view(request):
    """
    Registo com captcha validado no servidor.

    Fluxo:
      GET  → renderiza o form com captcha fresco
      POST → valida captcha + dados → cria utilizador via RegistoSerializer
             → faz login com sessão Django → guarda tokens JWT na sessão
             → redireciona para home

    O captcha é gerado pelo django-simple-captcha e verificado aqui,
    antes de qualquer lógica de negócio. Se falhar, o form é re-renderizado
    com um captcha novo e a mensagem de erro.
    """
    if request.method == 'POST':
        form = RegistoCaptchaForm(request.POST)

        if form.is_valid():
            # Captcha correcto — criar utilizador via serializer
            # (reutiliza toda a validação já existente: email único, etc.)
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

                # Login com sessão Django (resolve token_not_valid nas API calls)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                # Guardar tokens JWT na sessão para o JS os usar se precisar
                refresh = RefreshToken.for_user(user)
                request.session['jwt_access']  = str(refresh.access_token)
                request.session['jwt_refresh'] = str(refresh)

                return redirect(request.GET.get('next', '/'))

            else:
                # Erros do serializer (ex: email duplicado)
                # Passar ao template para mostrar inline
                serializer_errors = {
                    k: v[0] if isinstance(v, list) else v
                    for k, v in serializer.errors.items()
                }
                return render(request, 'users/signup.html', {
                    'form': form,
                    'serializer_errors': serializer_errors,
                })

        # Captcha inválido ou outros erros de form — re-renderizar com erros
        return render(request, 'users/signup.html', {'form': form})

    # GET
    form = RegistoCaptchaForm()
    return render(request, 'users/signup.html', {'form': form})
