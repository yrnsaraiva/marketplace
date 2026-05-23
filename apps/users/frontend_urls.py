from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('registo/', views.registo_view, name='registo'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
]