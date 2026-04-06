from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class RegistoSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2',
                  'telefone', 'provincia', 'cidade']

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
                  'provincia', 'cidade', 'papel', 'total_anuncios',
                  'avaliacao_media', 'date_joined']
        read_only_fields = ['id', 'email', 'papel', 'total_anuncios',
                            'avaliacao_media', 'date_joined']


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