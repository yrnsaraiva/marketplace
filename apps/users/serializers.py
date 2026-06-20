from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User

IDADE_MINIMA = 18


def validar_idade_minima(data_nascimento):
    """Levanta ValidationError se o utilizador tiver menos de 18 anos."""
    hoje = timezone.localdate()
    aniversario_este_ano = data_nascimento.replace(year=hoje.year)
    idade = hoje.year - data_nascimento.year
    if aniversario_este_ano > hoje:
        idade -= 1
    if idade < IDADE_MINIMA:
        raise serializers.ValidationError(
            f'É necessário ter pelo menos {IDADE_MINIMA} anos para se registar.'
        )


class RegistoSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2',
                  'telefone', 'data_nascimento', 'provincia', 'cidade']

    def validate_data_nascimento(self, value):
        if value is None:
            raise serializers.ValidationError('A data de nascimento é obrigatória.')
        validar_idade_minima(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {'password': 'As passwords não coincidem.'}
            )
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Este email já está registado.')
        return value

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'telefone', 'foto_perfil',
                  'data_nascimento', 'provincia', 'cidade', 'papel', 'total_anuncios',
                  'avaliacao_media', 'date_joined']
        read_only_fields = ['id', 'email', 'papel', 'total_anuncios',
                            'avaliacao_media', 'date_joined']

    def validate_data_nascimento(self, value):
        # Valida idade mínima também quando o perfil é actualizado (contas Google)
        if value is not None:
            validar_idade_minima(value)
        return value


class AlterarPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(required=True)
    password_nova = serializers.CharField(
        required=True, validators=[validate_password]
    )
    password_nova2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['password_nova'] != attrs['password_nova2']:
            raise serializers.ValidationError(
                {'password_nova': 'As passwords não coincidem.'}
            )
        return attrs