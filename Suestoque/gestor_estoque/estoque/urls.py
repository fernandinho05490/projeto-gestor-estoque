from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    dashboard_estoque, 
    registrar_movimentacao, 
    relatorio_vendas_view, 
    CustomLoginView,
    relatorios_view,
    exportar_relatorio_pdf,
    search_view,
    compras_view,
    gerar_ordem_de_compra,
    ordem_compra_list_view,
    ordem_compra_detail_view,
    ordem_compra_receber_view,
    pdv_view,
    search_variacoes_pdv,
    finalizar_venda_pdv # <-- Nova importação
)

urlpatterns = [
    # URLs do sistema
    path('', dashboard_estoque, name='dashboard_estoque'),
    path('search/', search_view, name='search_results'),
    path('movimentacao/registrar/', registrar_movimentacao, name='registrar_movimentacao'),

    # URLs de Compras
    path('compras/', compras_view, name='compras'),
    path('compras/gerar/', gerar_ordem_de_compra, name='gerar_ordem_de_compra'),
    path('compras/ordens/', ordem_compra_list_view, name='ordem_compra_list'),
    path('compras/ordens/<int:pk>/', ordem_compra_detail_view, name='ordem_compra_detail'),
    path('compras/ordens/<int:pk>/receber/', ordem_compra_receber_view, name='ordem_compra_receber'),

    # URLs do PDV
    path('pdv/', pdv_view, name='pdv'),
    path('pdv/search/', search_variacoes_pdv, name='pdv_search_variacoes'),
    path('pdv/finalizar/', finalizar_venda_pdv, name='pdv_finalizar_venda'), # <-- Nova rota da API

    # URLs de Relatórios
    path('relatorios/', relatorios_view, name='relatorios'),
    path('relatorio/vendas/<str:periodo>/', relatorio_vendas_view, name='relatorio_vendas'),
    path('relatorios/pdf/', exportar_relatorio_pdf, name='exportar_relatorio_pdf'),
    
    # URLs de Autenticação
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

