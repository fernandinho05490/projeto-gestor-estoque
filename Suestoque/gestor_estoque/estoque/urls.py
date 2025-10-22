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
    finalizar_venda_pdv,
    search_clientes_pdv,
    gerenciar_estoque_view,
    # Nossas novas views de CRM
    cliente_list_view,
    cliente_detail_view,
    analises_view,
    preparar_fatura_view,
    # ajustar_venda_view,
    busca_global_api_view,
)

urlpatterns = [
    # URLs do sistema
    path('', dashboard_estoque, name='dashboard_estoque'),
    path('search/', search_view, name='search_results'),
    path('movimentacao/registrar/', registrar_movimentacao, name='registrar_movimentacao'),
    path('analises/', analises_view, name='analises'),
    path('estoque/', gerenciar_estoque_view, name='gerenciar_estoque'),

    # URLs de Clientes (CRM)
    path('clientes/', cliente_list_view, name='cliente_list'),
    path('clientes/<int:pk>/', cliente_detail_view, name='cliente_detail'),

    # URLs de Compras
    path('compras/', compras_view, name='compras'),
    path('compras/gerar/', gerar_ordem_de_compra, name='gerar_ordem_de_compra'),
    path('compras/ordens/', ordem_compra_list_view, name='ordem_compra_list'),
    path('compras/ordens/<int:pk>/', ordem_compra_detail_view, name='ordem_compra_detail'),
    path('compras/ordens/<int:pk>/receber/', ordem_compra_receber_view, name='ordem_compra_receber'),

    # URLs do PDV
    path('pdv/', pdv_view, name='pdv'),
    path('pdv/search-variacoes/', search_variacoes_pdv, name='pdv_search_variacoes'),
    path('pdv/search-clientes/', search_clientes_pdv, name='pdv_search_clientes'),
    path('pdv/finalizar/', finalizar_venda_pdv, name='pdv_finalizar_venda'),

    # URLs de Relatórios
    path('relatorios/', relatorios_view, name='relatorios'),
    path('relatorio/vendas/<str:periodo>/', relatorio_vendas_view, name='relatorio_vendas'),
    path('relatorios/pdf/', exportar_relatorio_pdf, name='exportar_relatorio_pdf'),
    
    # prepara faturas
    path('fatura/preparar/<int:cliente_id>/<str:movimentacao_ids>/', preparar_fatura_view, name='preparar_fatura'),
    
    # URLs de Autenticação
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # nova rota para api de busca global
    path('api/busca-global/', busca_global_api_view, name='busca_global_api'),
]

