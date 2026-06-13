from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── allauth (login social + contas) ───────────────────────────────────
    # Inclui: /accounts/google/login/, /accounts/google/login/callback/, etc.
    path('accounts/', include('allauth.urls')),

    # ── API ───────────────────────────────────────────────────────────────
    path('api/v1/auth/',       include('apps.users.urls')),
    path('api/v1/categorias/', include('apps.categorias.urls')),
    path('api/v1/anuncios/',   include('apps.anuncios.urls')),
    path('api/v1/pagamentos/', include('apps.pagamentos.urls')),

    # ── Captcha ───────────────────────────────────────────────────────────
    path('captcha/',           include('captcha.urls')),

    # ── Templates (frontend) ──────────────────────────────────────────────
    path('',      include('apps.anuncios.frontend_urls')),
    path('conta/', include('apps.users.frontend_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
