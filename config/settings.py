from pathlib import Path
from decouple import config
from datetime import timedelta
from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-gx)%vh+q9h(4^r5y(fmqc1@1owc_5+y80^_=sr!43vbeigy3m)'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '*'
]

CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'http://localhost',
    'http://127.0.0.1',
]

# Application definition

INSTALLED_APPS = [
    # Apps Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Apps de terceiros
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',

    # Apps do projecto
    "apps.users.apps.UsersConfig",
    "apps.anuncios.apps.AnunciosConfig",
    "apps.pagamentos.apps.PagamentosConfig",
    "apps.categorias.apps.CategoriasConfig"
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ) if not DEBUG else (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '300/min',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


CELERY_BEAT_SCHEDULE = {
    'expirar-subscricoes': {
        'task': 'apps.pagamentos.tasks.expirar_subscricoes',
        'schedule': crontab(hour=0, minute=0),
    },
    'expirar-anuncios': {
        'task': 'apps.pagamentos.tasks.expirar_anuncios',
        'schedule': crontab(hour=1, minute=0),
    },
    'expirar-destaques': {
        'task': 'apps.pagamentos.tasks.expirar_destaques',
        'schedule': crontab(hour=2, minute=0),
    },
}

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'pt'

TIME_ZONE = 'Africa/Maputo'

USE_I18N = True

USE_TZ = True

USE_THOUSAND_SEPARATOR = True


AUTH_USER_MODEL = 'users.User'


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

# Pasta onde você coloca seus ficheiros estáticos do projeto
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Pasta onde o Django vai coletar tudo no deploy (collectstatic)
STATIC_ROOT = BASE_DIR / "staticfiles"


# MEDIA FILES (uploads)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

LOGIN_URL = '/conta/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='WARNING'),
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}


# PaySuite — Gateway de Pagamentos (https://paysuite.tech)
PAYSUITE_API_KEY = config('PAYSUITE_API_KEY', default='2059|OzpGtJH8LR5GY9TxenDdoexZHrWy1sF2cKR5G9ew8bd00523')
PAYSUITE_WEBHOOK_SECRET = config('PAYSUITE_WEBHOOK_SECRET', default='whsec_e9627dfb7ef4fd9fa3233e734abaa6ebe10cd95c3bc7b765')

# URL para onde o utilizador é redirecionado após o checkout PaySuite.
# Use o endpoint PaySuiteRetornoView — o <pk> é preenchido dinamicamente na view.
# Exemplo: a view IniciarCompraView passa o URL completo ao criar o pagamento.
PAYSUITE_RETURN_URL = config(
    'PAYSUITE_RETURN_URL',
    default='https://zonal.up.railway.app/api/pagamentos/retorno'
)

# URL do webhook que a PaySuite vai chamar (configurar no dashboard PaySuite).
PAYSUITE_CALLBACK_URL = config(
    'PAYSUITE_CALLBACK_URL',
    default='https://zonal.up.railway.app/api/pagamentos/webhook/paysuite/'
)