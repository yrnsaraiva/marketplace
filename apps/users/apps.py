from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'apps.users'

    def ready(self):
        # Registar os signal handlers definidos em views.py com @receiver
        import apps.users.views  # noqa: F401
