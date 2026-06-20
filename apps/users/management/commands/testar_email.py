"""
apps/users/management/commands/testar_email.py

Comando de diagnóstico para verificar a configuração de email.

Uso:
    python manage.py testar_email --para=o-teu-email@exemplo.com
    python manage.py testar_email --para=o-teu-email@exemplo.com --user-id=1
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Testa o envio de email e imprime diagnóstico detalhado'

    def add_arguments(self, parser):
        parser.add_argument('--para', required=True, help='Endereço de email de destino')
        parser.add_argument('--user-id', type=int, default=None,
                            help='ID de utilizador para testar o email de confirmação completo')

    def handle(self, *args, **options):
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.MIGRATE_HEADING('DIAGNÓSTICO DE EMAIL — ZONAL'))
        self.stdout.write('─' * 60)

        # 1. Mostrar configuração actual
        self._mostrar_config()

        # 2. Testar email simples
        self._testar_email_simples(options['para'])

        # 3. Se user-id fornecido, testar email de confirmação completo
        if options['user_id']:
            self._testar_email_confirmacao(options['user_id'], options['para'])

        self.stdout.write('─' * 60 + '\n')

    def _mostrar_config(self):
        self.stdout.write('\n[1] Configuração actual em settings.py:\n')
        campos = [
            'EMAIL_BACKEND',
            'EMAIL_HOST',
            'EMAIL_PORT',
            'EMAIL_USE_TLS',
            'EMAIL_USE_SSL',
            'EMAIL_HOST_USER',
            'DEFAULT_FROM_EMAIL',
            'FRONTEND_URL',
        ]
        for campo in campos:
            valor = getattr(settings, campo, '❌  NÃO DEFINIDO')
            # Mascarar password
            if 'PASSWORD' in campo and valor:
                valor = '***'
            self.stdout.write(f'   {campo:<30} = {valor}')

    def _testar_email_simples(self, para):
        self.stdout.write(f'\n[2] A enviar email de teste para {para} ...\n')
        try:
            enviados = send_mail(
                subject='[Zonal] Teste de email',
                message='Este é um email de teste do sistema Zonal. Se recebeu este email, a configuração está correcta.',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@zonal.co.mz'),
                recipient_list=[para],
                fail_silently=False,
            )
            if enviados:
                self.stdout.write(self.style.SUCCESS('   ✅  Email enviado com sucesso!'))
            else:
                self.stdout.write(self.style.WARNING('   ⚠️   send_mail devolveu 0 — email não enviado sem erro.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌  Erro: {e}'))
            self._sugerir_solucao(str(e))

    def _testar_email_confirmacao(self, user_id, para):
        self.stdout.write(f'\n[3] A testar email de confirmação completo para utilizador #{user_id} ...\n')
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'   ❌  Utilizador #{user_id} não encontrado.'))
            return

        # Substituir email temporariamente para enviar para o endereço de teste
        email_original = user.email
        user.email = para

        from apps.users.emails import enviar_email_confirmacao
        enviado, erro = enviar_email_confirmacao(user)

        user.email = email_original  # restaurar (não guardar)

        if enviado:
            self.stdout.write(self.style.SUCCESS(f'   ✅  Email de confirmação enviado para {para}'))
        else:
            self.stdout.write(self.style.ERROR(f'   ❌  Falhou: {erro}'))
            self._sugerir_solucao(erro or '')

    def _sugerir_solucao(self, erro: str):
        self.stdout.write('\n   💡 Sugestões:\n')
        erro_lower = erro.lower()

        if 'connection refused' in erro_lower or 'errno 111' in erro_lower:
            self.stdout.write('   → EMAIL_HOST ou EMAIL_PORT incorrectos, ou servidor SMTP inacessível.')
            self.stdout.write('   → Para desenvolvimento: EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"')

        elif 'authentication' in erro_lower or '535' in erro_lower or 'username and password' in erro_lower:
            self.stdout.write('   → Credenciais SMTP incorrectas.')
            self.stdout.write('   → Para Gmail: use uma App Password (não a password normal da conta).')
            self.stdout.write('   → Gerar em: https://myaccount.google.com/apppasswords')

        elif 'ssl' in erro_lower or 'tls' in erro_lower:
            self.stdout.write('   → Conflito SSL/TLS. Verifique:')
            self.stdout.write('     PORT 587  → EMAIL_USE_TLS = True,  EMAIL_USE_SSL = False')
            self.stdout.write('     PORT 465  → EMAIL_USE_TLS = False, EMAIL_USE_SSL = True')

        elif 'timeout' in erro_lower:
            self.stdout.write('   → Timeout de ligação. Verifique firewall ou porta bloqueada.')

        elif 'frontend_url' in erro_lower or 'url base' in erro_lower:
            self.stdout.write('   → Adicione FRONTEND_URL = "https://zonal.co.mz" em settings.py')

        else:
            self.stdout.write('   → Verifique as definições EMAIL_* em settings.py')
            self.stdout.write('   → Documentação Django: https://docs.djangoproject.com/en/stable/topics/email/')
