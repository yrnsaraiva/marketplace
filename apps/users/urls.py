from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('registo/', views.RegistoView.as_view(), name='registo'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    path('alterar-password/', views.AlterarPasswordView.as_view(), name='alterar-password'),
]