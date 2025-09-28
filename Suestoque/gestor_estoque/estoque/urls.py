# estoque/urls.py 

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    dashboard_estoque, registrar_movimentacao, 
    relatorio_vendas_view, exportar_relatorio_pdf, CustomLoginView
)

urlpatterns = [
    # A URL '' corresponde à raiz do site (página inicial)
    path('', dashboard_estoque, name='dashboard_estoque'),
    path('registrar_movimentacao/', registrar_movimentacao, name='registrar_movimentacao'),
    path('relatorio/vendas/<str:periodo>/', relatorio_vendas_view, name='relatorio_vendas'),

    # --- INÍCIO: NOVAS URLS DE AUTENTICAÇÃO ---
    path('login/', CustomLoginView.as_view(), name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('relatorios/', views.relatorios_view, name='relatorios'),

    path('relatorios/pdf/', views.exportar_relatorio_pdf, name='exportar_relatorio_pdf'),
    # --- FIM: NOVAS URLS DE AUTENTICAÇÃO ---
]