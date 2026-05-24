"""
apps/users/views.py

Contém apenas as views de autenticação API.
"""
import logging

from django.contrib.auth import authenticate
from django.shortcuts import render
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import AlterarPasswordSerializer, PerfilSerializer, RegistoSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API - Autenticação
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
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')

        if not email or not password:
            return Response(
                {'erro': 'Email e password são obrigatórios.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user_obj = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(
                {'erro': 'Credenciais inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(request, username=user_obj.username, password=password)

        if not user:
            return Response(
                {'erro': 'Credenciais inválidas.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.bloqueado:
            return Response(
                {'erro': f'Conta bloqueada. Motivo: {user.motivo_bloqueio}'},
                status=status.HTTP_403_FORBIDDEN
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
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass # token inválido ou já na blacklist - não é erro crítico
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
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['password_nova'])
        user.save()

        # Revogar token actual após mudança de password
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                RefreshToken(refresh_token).blacklist()
        except Exception:
            pass

        return Response({'mensagem': 'Password alterada com sucesso. Faça login novamente.'})


# ---------------------------------------------------------------------------
# Frontend - vistas de template simples
# (a lógica pesada está em apps/anuncios/views.py)
# ---------------------------------------------------------------------------

def login_template_view(request):
    """Renderiza o template de login (autenticação feita via JS + API JWT)."""
    return render(request, 'users/login.html')


def signup_template_view(request):
    """Renderiza o template de registo."""
    return render(request, 'users/signup.html')