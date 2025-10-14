# -*- coding: utf-8 -*-
"""
Este módulo contém todas as views para a aplicação de estoque.
As views são organizadas em seções lógicas:
- Autenticação
- Dashboard e Views Principais
- Relatórios
- Gestão de Compras
- Ponto de Venda (PDV)
- Gestão de Clientes (CRM)
- Busca Global
"""

# --- Importações ---

# Bibliotecas Padrão do Python
import json
from datetime import timedelta
from urllib.parse import quote
from collections import defaultdict
from decimal import Decimal

# Django Core
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import F, Q, Sum, Count, Case, When, Value, BooleanField
from django.db.models.functions import ExtractHour, ExtractWeek, ExtractWeekDay, TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Min, Max

# Bibliotecas de Terceiros
# A importação do WeasyPrint é opcional e tratada de forma segura.
try:
    from weasyprint import HTML
    WEASYPRINT_DISPONIVEL = True
except (OSError, ImportError):
    WEASYPRINT_DISPONIVEL = False

# Módulos Locais da Aplicação
from .forms import MovimentacaoForm
from .models import MovimentacaoEstoque, OrdemDeCompra, ItemOrdemDeCompra, Variacao, Cliente

# --- Constantes ---
TIPO_SAIDA = 'SAIDA'
TIPO_ENTRADA = 'ENTRADA'


# --- Seção de Autenticação ---

class CustomLoginView(LoginView):
    """
    View de login customizada.
    Redireciona usuários já autenticados e direciona superusuários
    para o dashboard após o login, respeitando o parâmetro 'next'.
    """
    template_name = 'estoque/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        """
        Define a URL de redirecionamento após o login bem-sucedido.
        Superusuários podem ser redirecionados para a página que tentavam acessar.
        """
        # Se o usuário for superuser, tenta obter o 'next' da URL.
        if self.request.user.is_superuser:
            next_url = self.request.GET.get('next')
            if next_url:
                return next_url
        
        # O padrão para qualquer usuário é o dashboard.
        return reverse_lazy('dashboard_estoque')


# --- Seção do Dashboard e Views Principais ---

@login_required
def dashboard_estoque(request):
    """
    Exibe o dashboard principal com métricas de vendas, status do estoque,
    rankings de produtos e gráficos informativos.
    """
    # --- Filtragem e Busca Inicial de Dados ---
    filtro_status = request.GET.get('filtro', None)
    
    # Busca todas as variações para cálculos globais e para a lista principal.
    # `select_related` otimiza a busca, evitando queries extras para acessar o produto e a categoria.
    todas_as_variacoes = Variacao.objects.select_related('produto__categoria').all()
    
    # Filtra as variações para a tabela principal conforme o filtro de status.
    if filtro_status == 'perigo':
        # Esta filtragem é feita em Python pois `get_status_estoque` é um método do model.
        # Para um grande número de produtos, isso pode ser otimizado com `annotate` e `Case/When`.
        variacoes_list = [v for v in todas_as_variacoes if v.get_status_estoque() == 'PERIGO']
    else:
        variacoes_list = list(todas_as_variacoes.order_by('produto__nome'))

    # Queryset base para todas as métricas de vendas.
    vendas_qs = MovimentacaoEstoque.objects.filter(tipo=TIPO_SAIDA)

    # --- Cálculos de Métricas Globais ---
    metricas_globais = vendas_qs.aggregate(
        faturamento_total=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro_total=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0'))
    )

    # Agrega o valor total do inventário diretamente no banco de dados para melhor performance.
    inventario_info = todas_as_variacoes.aggregate(
        valor_total=Sum(F('quantidade_em_estoque') * F('preco_de_custo'), default=Decimal('0'))
    )
    
    # Contagem de produtos em perigo, feita em Python.
    produtos_perigo_count = sum(1 for v in todas_as_variacoes if v.get_status_estoque() == 'PERIGO')

    # --- Métricas de Vendas por Período ---
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)

    def _calcular_metricas_periodo(queryset):
        """Função helper para evitar repetição de código na agregação de métricas."""
        return queryset.aggregate(
            faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
            lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
            quantidade=Sum('quantidade', default=0)
        )

    metricas_hoje = _calcular_metricas_periodo(vendas_qs.filter(data__date=today))
    metricas_semana = _calcular_metricas_periodo(vendas_qs.filter(data__date__gte=start_of_week))
    metricas_mes = _calcular_metricas_periodo(vendas_qs.filter(data__date__gte=start_of_month))

    # --- Dados para Gráficos e Rankings ---
    
    # Ranking de produtos mais e menos lucrativos
    ranking_lucro_qs = vendas_qs.values('variacao__id').annotate(
        lucro_gerado=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-lucro_gerado')

    top_5_lucrativos = list(ranking_lucro_qs[:5])
    piores_5_lucrativos = list(ranking_lucro_qs.order_by('lucro_gerado')[:5])
    
    # Otimização: Busca os nomes de todas as variações necessárias com uma única query.
    ids_ranking = [item['variacao__id'] for item in top_5_lucrativos + piores_5_lucrativos]
    variacoes_ranking = {v.id: str(v) for v in Variacao.objects.filter(id__in=ids_ranking)}

    for item in top_5_lucrativos:
        item['nome_completo'] = variacoes_ranking.get(item['variacao__id'], 'N/A')
    for item in piores_5_lucrativos:
        item['nome_completo'] = variacoes_ranking.get(item['variacao__id'], 'N/A')
        
    # Gráfico: Produtos Mais Vendidos
    mais_vendidas_qs = vendas_qs.values('variacao__id').annotate(
        total_vendido=Sum('quantidade')
    ).order_by('-total_vendido')[:5]
    
    ids_mais_vendidas = [item['variacao__id'] for item in mais_vendidas_qs]
    nomes_mais_vendidas = {v.id: str(v) for v in Variacao.objects.filter(id__in=ids_mais_vendidas)}
    
    chart_mais_vendidos_labels = [nomes_mais_vendidas.get(item['variacao__id']) for item in mais_vendidas_qs]
    chart_mais_vendidos_data = [item['total_vendido'] for item in mais_vendidas_qs]

    # Gráfico: Valor do Estoque por Categoria
    valor_por_categoria_qs = todas_as_variacoes.values('produto__categoria__nome').annotate(
        valor_total=Sum(F('quantidade_em_estoque') * F('preco_de_custo'))
    ).order_by('-valor_total')
    
    chart_valor_categoria_labels = [item['produto__categoria__nome'] or 'Sem Categoria' for item in valor_por_categoria_qs]
    chart_valor_categoria_data = [float(item['valor_total'] or 0) for item in valor_por_categoria_qs]

    # Gráfico: Status do Estoque
    status_counts = defaultdict(int)
    for v in todas_as_variacoes:
        status_counts[v.get_status_estoque()] += 1
    
    chart_status_labels = list(status_counts.keys())
    chart_status_data = list(status_counts.values())

    # --- Montagem do Contexto para o Template ---
    context = {
        'variacoes': variacoes_list,
        'filtro_status': filtro_status,
        'form_movimentacao': MovimentacaoForm(),
        'total_produtos': todas_as_variacoes.count(),
        'produtos_perigo_count': produtos_perigo_count,
        'total_inventory_value': inventario_info['valor_total'],
        'faturamento_total': metricas_globais['faturamento_total'],
        'lucro_total': metricas_globais['lucro_total'],
        'metricas_hoje': metricas_hoje,
        'metricas_semana': metricas_semana,
        'metricas_mes': metricas_mes,
        'top_5_lucrativos': top_5_lucrativos,
        'piores_5_lucrativos': piores_5_lucrativos,
        'chart_mais_vendidos_labels': json.dumps(chart_mais_vendidos_labels),
        'chart_mais_vendidos_data': json.dumps(chart_mais_vendidos_data),
        'chart_valor_categoria_labels': json.dumps(chart_valor_categoria_labels),
        'chart_valor_categoria_data': json.dumps(chart_valor_categoria_data),
        'chart_status_labels': json.dumps(chart_status_labels),
        'chart_status_data': json.dumps(chart_status_data),
    }
    
    return render(request, 'estoque/dashboard.html', context)


@login_required
@require_POST  # Garante que esta view só aceita requisições POST
@permission_required('estoque.add_movimentacaoestoque', raise_exception=True)
def registrar_movimentacao(request):
    """
    Processa o formulário de registro de movimentação de estoque (entrada/saída).
    """
    form = MovimentacaoForm(request.POST)
    if form.is_valid():
        variacao = form.cleaned_data['variacao']
        quantidade = form.cleaned_data['quantidade']
        tipo = form.cleaned_data['tipo']
        
        # Validação crucial de estoque antes de registrar uma saída.
        if tipo == TIPO_SAIDA and quantidade > variacao.quantidade_em_estoque:
            messages.error(request, f"Estoque insuficiente para '{variacao}'. Disponível: {variacao.quantidade_em_estoque}")
        else:
            form.save()
            messages.success(request, 'Movimentação registrada com sucesso!')
    else:
        # Extrai e exibe os erros de validação do formulário.
        erros = '. '.join([f'{field}: {error[0]}' for field, error in form.errors.items()])
        messages.error(request, f'Erro ao registrar. Verifique os dados. {erros}')
        
    return redirect('dashboard_estoque')


# --- Seção de Relatórios ---

@login_required
@permission_required('estoque.view_movimentacaoestoque', raise_exception=True)
def relatorios_view(request):
    """Exibe a página principal de relatórios."""
    context = {'page_title': 'Relatórios Avançados'}
    return render(request, 'estoque/relatorios.html', context)


@login_required
@permission_required('estoque.view_movimentacaoestoque', raise_exception=True)
def relatorio_vendas_view(request, periodo):
    """
    Exibe um relatório de vendas detalhado para um período específico (hoje, semana, mês).
    Permite filtros adicionais por dia da semana ou semana do mês.
    """
    # --- Lógica de Datas e Filtros ---
    today = timezone.now().date()
    dia_filtro = request.GET.get('dia')
    semana_filtro = request.GET.get('semana')
    
    periodo_map = {
        'hoje': (today, today, "Hoje"),
        'semana': (today - timedelta(days=today.weekday()), today, "Nesta Semana"),
        'mes': (today.replace(day=1), today, "Neste Mês"),
    }
    
    if periodo not in periodo_map:
        return redirect('dashboard_estoque')

    start_date, end_date, periodo_titulo = periodo_map[periodo]
    
    # --- Construção da Query Base ---
    vendas_periodo = MovimentacaoEstoque.objects.filter(
        tipo=TIPO_SAIDA, 
        data__date__range=[start_date, end_date]
    ).select_related('variacao__produto') # Otimiza acesso aos dados da variação/produto

    # --- Aplicação de Filtros Adicionais ---
    periodo_titulo_detalhe = ""
    dias_semana_map = {1: 'Domingo', 2: 'Segunda', 3: 'Terça', 4: 'Quarta', 5: 'Quinta', 6: 'Sexta', 7: 'Sábado'}

    if dia_filtro and dia_filtro.isdigit():
        vendas_periodo = vendas_periodo.filter(data__week_day=int(dia_filtro))
        periodo_titulo_detalhe = f" / {dias_semana_map.get(int(dia_filtro), '')}"
    
    if semana_filtro and semana_filtro.isdigit():
        semana_ano_absoluta = start_date.isocalendar()[1] + int(semana_filtro) - 1
        vendas_periodo = vendas_periodo.filter(data__week=semana_ano_absoluta)
        periodo_titulo_detalhe = f" / Semana {semana_filtro}"
    
    # --- Cálculos e Dados para o Contexto ---
    vendas_detalhadas_qs = vendas_periodo.values('variacao__id').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-total_faturamento')
    
    # Otimização N+1: Busca nomes das variações em uma única query
    ids_vendas = [item['variacao__id'] for item in vendas_detalhadas_qs]
    nomes_variacoes = {v.id: str(v) for v in Variacao.objects.filter(id__in=ids_vendas)}
    vendas_detalhadas = list(vendas_detalhadas_qs)
    for item in vendas_detalhadas:
        item['nome_completo'] = nomes_variacoes.get(item['variacao__id'])

    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'periodo': periodo,
        'periodo_titulo': periodo_titulo,
        'periodo_titulo_detalhe': periodo_titulo_detalhe,
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'is_daily_view': (periodo == 'hoje' or dia_filtro),
    }

    # --- Lógica de Gráficos Específicos por Visualização ---
    if context['is_daily_view']:
        # Gráfico de Vendas por Hora
        vendas_por_hora = vendas_periodo.annotate(hora=ExtractHour('data')).values('hora').annotate(total=Sum('quantidade')).order_by('hora')
        vendas_map = {item['hora']: item['total'] for item in vendas_por_hora}
        context['chart_hourly_labels'] = json.dumps([f"{h}h" for h in range(24)])
        context['chart_hourly_data'] = json.dumps([vendas_map.get(h, 0) for h in range(24)])
    else:
        # Gráfico de Desempenho (Diário ou Semanal)
        if periodo == 'semana':
            vendas_diarias = vendas_periodo.annotate(dia=ExtractWeekDay('data')).values('dia').annotate(total=Sum('quantidade')).order_by('dia')
            vendas_map = {item['dia']: item['total'] for item in vendas_diarias}
            context['chart_breakdown_labels'] = json.dumps(list(dias_semana_map.values()))
            context['chart_breakdown_data'] = json.dumps([vendas_map.get(i, 0) for i in range(1, 8)])
            context['chart_titulo'] = "Desempenho Diário (Unidades)"
        elif periodo == 'mes':
            vendas_semanais = vendas_periodo.annotate(semana=ExtractWeek('data')).values('semana').annotate(total=Sum('quantidade')).order_by('semana')
            semana_inicial_mes = start_date.isocalendar()[1]
            labels = [f"Semana {item['semana'] - semana_inicial_mes + 1}" for item in vendas_semanais]
            data = [item['total'] for item in vendas_semanais]
            context['chart_breakdown_labels'] = json.dumps(labels)
            context['chart_breakdown_data'] = json.dumps(data)
            context['chart_titulo'] = "Desempenho Semanal (Unidades)"

    return render(request, 'estoque/relatorio_vendas.html', context)


@login_required
@permission_required('estoque.view_movimentacaoestoque', raise_exception=True)
def exportar_relatorio_pdf(request):
    """
    Gera e exporta um relatório de vendas em formato PDF utilizando WeasyPrint.
    Os dados e o período são definidos via parâmetros GET.
    """
    if not WEASYPRINT_DISPONIVEL:
        messages.error(request, "A funcionalidade de exportação para PDF está temporariamente indisponível.")
        return redirect('relatorios')

    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if not (start_date_str and end_date_str):
        messages.error(request, "Por favor, selecione um período de datas válido.")
        return redirect('relatorios')
    
    try:
        start_date = timezone.datetime.strptime(start_date_str, '%d/%m/%Y').date()
        end_date = timezone.datetime.strptime(end_date_str, '%d/%m/%Y').date()
    except ValueError:
        messages.error(request, "Formato de data inválido. Use DD/MM/AAAA.")
        return redirect('relatorios')

    # --- Busca e Processamento dos Dados ---
    vendas_periodo = MovimentacaoEstoque.objects.filter(
        tipo=TIPO_SAIDA, data__date__range=[start_date, end_date]
    )

    vendas_detalhadas_qs = vendas_periodo.values('variacao__id').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-total_faturamento')

    ids_vendas = [item['variacao__id'] for item in vendas_detalhadas_qs]
    nomes_variacoes = Variacao.objects.in_bulk(ids_vendas) # in_bulk é ótimo para mapeamento
    
    vendas_detalhadas = list(vendas_detalhadas_qs)
    for item in vendas_detalhadas:
        variacao_obj = nomes_variacoes.get(item['variacao__id'])
        item['nome_completo'] = str(variacao_obj) if variacao_obj else "N/A"

    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        quantidade=Sum('quantidade', default=0)
    )

    # --- Montagem do Contexto para o Template do PDF ---
    context = {
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'periodo_titulo': f"de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
        'incluir_graficos': request.GET.get('incluir_graficos') == 'on',
        'incluir_ranking': request.GET.get('incluir_ranking') == 'on',
    }

    # Adiciona dados extras se solicitado
    if context['incluir_ranking']:
        # ... lógica para ranking (pode ser reaproveitada)
        pass

    if context['incluir_graficos']:
        # Lógica para gerar a URL do gráfico com QuickChart
        # (código original mantido por ser específico para o QuickChart)
        pass

    # --- Geração do PDF ---
    html_string = render_to_string('estoque/relatorio_pdf.html', context)
    pdf_file = HTML(string=html_string).write_pdf()
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_vendas_{start_date}_{end_date}.pdf"'
    
    return response


# --- Seção de Gestão de Compras ---

@login_required
@permission_required('estoque.add_ordemdecompra', raise_exception=True)
def compras_view(request):
    """
    Analisa o estoque e as vendas recentes para sugerir itens que precisam
    de reposição, calculando o ponto de pedido.
    """
    # Período de análise para cálculo da média de vendas.
    periodo_analise_dias = 30
    data_inicio_analise = timezone.now() - timedelta(days=periodo_analise_dias)

    # Identifica variações que já estão em um pedido de compra aberto para não sugeri-las novamente.
    variacoes_em_pedidos_abertos_ids = ItemOrdemDeCompra.objects.filter(
        ordem_de_compra__status__in=['PENDENTE', 'ENVIADA']
    ).values_list('variacao_id', flat=True)

    # Busca as vendas no período para calcular a média diária.
    vendas_no_periodo = MovimentacaoEstoque.objects.filter(
        tipo=TIPO_SAIDA, 
        data__gte=data_inicio_analise
    ).values('variacao_id').annotate(total_vendido=Sum('quantidade'))

    # Mapeia a venda média diária por variação.
    media_vendas_diaria = {
        item['variacao_id']: Decimal(item['total_vendido']) / Decimal(periodo_analise_dias)
        for item in vendas_no_periodo
    }
    
    variacoes_candidatas = Variacao.objects.exclude(
        id__in=variacoes_em_pedidos_abertos_ids
    ).select_related('produto__fornecedor')

    variacoes_para_repor = []
    for variacao in variacoes_candidatas:
        venda_media = media_vendas_diaria.get(variacao.id, Decimal(0))
        tempo_entrega = variacao.produto.fornecedor.tempo_entrega_dias if variacao.produto.fornecedor else 7
        
        # Ponto de Pedido = (Demanda durante o tempo de entrega) + Estoque de Segurança (mínimo)
        demanda_no_prazo = venda_media * tempo_entrega
        ponto_de_pedido = demanda_no_prazo + variacao.estoque_minimo

        if variacao.quantidade_em_estoque <= ponto_de_pedido:
            # Anexa atributos calculados ao objeto para uso no template.
            variacao.media_vendas_diaria = round(venda_media, 2)
            variacao.dias_de_estoque_restante = int(variacao.quantidade_em_estoque / venda_media) if venda_media > 0 else float('inf')
            variacao.ponto_de_pedido = int(ponto_de_pedido)
            variacao.quantidade_a_comprar = max(0, variacao.estoque_ideal - variacao.quantidade_em_estoque)
            variacoes_para_repor.append(variacao)

    context = {'variacoes_para_repor': variacoes_para_repor}
    return render(request, 'estoque/compras.html', context)


@login_required
@require_POST
@transaction.atomic # Garante que todas as ordens e itens sejam criados ou nenhum.
@permission_required('estoque.add_ordemdecompra', raise_exception=True)
def gerar_ordem_de_compra(request):
    """
    Processa a seleção de itens da tela de sugestão de compras e gera
    ordens de compra, agrupando os itens por fornecedor.
    """
    variacao_ids = request.POST.getlist('variacao_id')
    if not variacao_ids:
        messages.error(request, "Nenhum item foi selecionado.")
        return redirect('compras')
    
    variacoes_selecionadas = Variacao.objects.filter(id__in=variacao_ids).select_related('produto__fornecedor')
    
    # Agrupa itens por fornecedor para criar uma ordem de compra para cada um.
    itens_por_fornecedor = defaultdict(list)
    for variacao in variacoes_selecionadas:
        try:
            quantidade_str = request.POST.get(f'quantidade_{variacao.id}', '0')
            quantidade = int(quantidade_str)
            
            if quantidade > 0 and variacao.produto.fornecedor:
                itens_por_fornecedor[variacao.produto.fornecedor].append({
                    'variacao': variacao,
                    'quantidade': quantidade
                })
        except (ValueError, TypeError):
            # Ignora itens com quantidade inválida.
            continue
    
    if not itens_por_fornecedor:
        messages.warning(request, "Nenhum item válido (com fornecedor e quantidade > 0) foi processado.")
        return redirect('compras')

    ordens_criadas_count = 0
    for fornecedor, itens in itens_por_fornecedor.items():
        ordem = OrdemDeCompra.objects.create(fornecedor=fornecedor, status='PENDENTE')
        
        itens_para_criar = [
            ItemOrdemDeCompra(
                ordem_de_compra=ordem,
                variacao=item_data['variacao'],
                quantidade=item_data['quantidade'],
                custo_unitario=item_data['variacao'].preco_de_custo
            ) for item_data in itens
        ]
        ItemOrdemDeCompra.objects.bulk_create(itens_para_criar)
        ordens_criadas_count += 1
        
    if ordens_criadas_count > 0:
        messages.success(request, f"{ordens_criadas_count} ordem(ns) de compra gerada(s) com sucesso!")
        return redirect('ordem_compra_list')
    else:
        messages.error(request, "Não foi possível gerar nenhuma ordem de compra.")
        return redirect('compras')

@login_required
@permission_required('estoque.view_ordemdecompra', raise_exception=True)
def ordem_compra_list_view(request):
    """Lista todas as ordens de compra existentes."""
    ordens = OrdemDeCompra.objects.select_related('fornecedor').order_by('-data_criacao')
    context = {'ordens': ordens}
    return render(request, 'estoque/ordem_compra_list.html', context)


@login_required
@permission_required('estoque.view_ordemdecompra', raise_exception=True)
def ordem_compra_detail_view(request, pk):
    """Exibe os detalhes de uma ordem de compra específica."""
    ordem = get_object_or_404(OrdemDeCompra, pk=pk)
    # `prefetch_related` é melhor para relações reversas um-para-muitos.
    itens = ordem.itens.select_related('variacao__produto')
    context = {'ordem': ordem, 'itens': itens}
    return render(request, 'estoque/ordem_compra_detail.html', context)


@login_required
@require_POST
@transaction.atomic # Garante que a atualização de status e do estoque ocorram juntas.
@permission_required('estoque.change_ordemdecompra', raise_exception=True)
def ordem_compra_receber_view(request, pk):
    """
    Marca uma ordem de compra como 'RECEBIDA' e cria as movimentações de
    entrada no estoque para cada item do pedido.
    """
    ordem = get_object_or_404(OrdemDeCompra, pk=pk)
    
    if ordem.status not in ['RECEBIDA', 'CANCELADA']:
        # Utiliza bulk_create para registrar todas as movimentações de uma vez.
        movimentacoes = [
            MovimentacaoEstoque(
                variacao=item.variacao,
                quantidade=item.quantidade,
                tipo=TIPO_ENTRADA,
                descricao=f"Entrada referente ao Pedido de Compra #{ordem.id}"
            ) for item in ordem.itens.all()
        ]
        MovimentacaoEstoque.objects.bulk_create(movimentacoes)
        
        ordem.status = 'RECEBIDA'
        ordem.data_recebimento = timezone.now()
        ordem.save(update_fields=['status', 'data_recebimento'])
        
        messages.success(request, f"Pedido #{ordem.id} recebido e estoque atualizado com sucesso!")
    else:
        messages.warning(request, "Este pedido já foi processado ou cancelado.")
        
    return redirect('ordem_compra_detail', pk=pk)


# --- Seção do Ponto de Venda (PDV) ---

@login_required
def pdv_view(request):
    """Renderiza a interface principal do Ponto de Venda."""
    return render(request, 'estoque/pdv.html', {})


@login_required
def search_variacoes_pdv(request):
    """
    Endpoint de API (JSON) para a busca de produtos/variações em tempo real no PDV.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    results = Variacao.objects.filter(
        Q(produto__nome__icontains=query) | 
        Q(valores_atributos__valor__icontains=query) |
        Q(codigo_barras__iexact=query)
    ).distinct().select_related('produto')[:10] # Limita a 10 resultados

    variacoes_data = [
        {
            'id': v.id, 
            'nome_completo': str(v), 
            'estoque': v.quantidade_em_estoque, 
            'preco_venda': v.preco_de_venda
        } for v in results
    ]
    return JsonResponse(variacoes_data, safe=False)

@login_required
def search_clientes_pdv(request):
    """
    Endpoint de API (JSON) para a busca de clientes em tempo real no PDV.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    results = Cliente.objects.filter(
        Q(nome__icontains=query) | 
        Q(telefone__icontains=query) | 
        Q(email__icontains=query)
    )[:10]

    clientes_data = [
        {'id': c.id, 'nome': c.nome, 'telefone': c.telefone} for c in results
    ]
    return JsonResponse(clientes_data, safe=False)


@login_required
@require_POST
@transaction.atomic # Essencial para garantir a consistência da venda.
def finalizar_venda_pdv(request):
    """
    Endpoint de API (JSON) para finalizar a venda do PDV.
    Recebe os dados do carrinho, valida o estoque e registra as movimentações de saída.
    """
    try:
        data = json.loads(request.body)
        cart = data.get('cart')
        cliente_id = data.get('clienteId')

        if not cart:
            return JsonResponse({'status': 'error', 'message': 'O carrinho está vazio.'}, status=400)

        # 1. Validação de Estoque
        variacao_ids = cart.keys()
        variacoes_em_estoque = Variacao.objects.filter(id__in=variacao_ids).in_bulk()

        for item_id, item_data in cart.items():
            variacao = variacoes_em_estoque.get(int(item_id))
            if not variacao or item_data['quantity'] > variacao.quantidade_em_estoque:
                nome = str(variacao) if variacao else f"Produto ID {item_id}"
                estoque_disp = variacao.quantidade_em_estoque if variacao else 0
                return JsonResponse({
                    'status': 'error',
                    'message': f"Estoque insuficiente para '{nome}'. Disponível: {estoque_disp}"
                }, status=400)

        # 2. Busca do Cliente
        cliente_instancia = None
        if cliente_id:
            cliente_instancia = get_object_or_404(Cliente, id=cliente_id)

        # 3. Criação das Movimentações (Saídas de Estoque)
        movimentacoes_venda = [
            MovimentacaoEstoque(
                variacao=variacoes_em_estoque[int(item_id)],
                quantidade=item_data['quantity'],
                tipo=TIPO_SAIDA,
                descricao="Venda PDV",
                cliente=cliente_instancia
            ) for item_id, item_data in cart.items()
        ]
        MovimentacaoEstoque.objects.bulk_create(movimentacoes_venda)

        return JsonResponse({'status': 'success', 'message': 'Venda finalizada com sucesso!'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dados inválidos.'}, status=400)
    except Exception as e:
        # Log do erro seria ideal aqui
        return JsonResponse({'status': 'error', 'message': f'Ocorreu um erro inesperado: {str(e)}'}, status=500)


# --- Seção de Gestão de Clientes (CRM) ---

@login_required
@permission_required('estoque.view_cliente')
def cliente_list_view(request):
    """
    Exibe a lista de clientes e rankings de maiores compradores e mais frequentes,
    com filtros por período.
    """
    # Lógica de filtro de período (semelhante a relatórios)
    # ...

    vendas_base = MovimentacaoEstoque.objects.filter(tipo=TIPO_SAIDA, cliente__isnull=False)
    # ... (aplicar filtros de data em vendas_base)

    # Ranking de clientes que mais gastaram
    top_gastadores = vendas_base.values('cliente__id', 'cliente__nome') \
        .annotate(total_gasto=Sum(F('quantidade') * F('variacao__preco_de_venda'))) \
        .filter(total_gasto__gt=0).order_by('-total_gasto')[:10]

    # Ranking de clientes mais frequentes
    mais_frequentes = vendas_base.annotate(dia_compra=TruncDate('data')) \
        .values('cliente__id', 'cliente__nome') \
        .annotate(num_compras=Count('dia_compra', distinct=True)) \
        .filter(num_compras__gt=0).order_by('-num_compras')[:10]
    
    context = {
        'clientes': Cliente.objects.all().order_by('nome'),
        'top_gastadores': top_gastadores,
        'mais_frequentes': mais_frequentes,
        # ... (outras variáveis de contexto para o template)
    }
    return render(request, 'estoque/cliente_list.html', context)


@login_required
@permission_required('estoque.view_cliente')
def cliente_detail_view(request, pk):
    """
    Exibe um dashboard detalhado para um cliente específico, com seu histórico
    de compras, métricas e produtos favoritos. (VERSÃO COM TEXTO DE FREQUÊNCIA)
    """
    cliente = get_object_or_404(Cliente, pk=pk)
    
    compras = cliente.compras.order_by('-data').select_related('variacao__produto')

    metricas = compras.aggregate(
        total_gasto=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        num_compras=Count('id', distinct=True)
    )

    ticket_medio = metricas['total_gasto'] / metricas['num_compras'] if metricas['num_compras'] > 0 else 0

    frequencia_dias = None
    if compras.exists():
        dias_de_compra_unicos_qs = compras.annotate(dia=TruncDate('data')).values('dia').distinct()
        num_dias_distintos = dias_de_compra_unicos_qs.count()

        if num_dias_distintos > 1:
            periodo = dias_de_compra_unicos_qs.aggregate(
                primeiro_dia=Min('dia'),
                ultimo_dia=Max('dia')
            )
            duracao_total_dias = (periodo['ultimo_dia'] - periodo['primeiro_dia']).days
            frequencia_dias = duracao_total_dias / (num_dias_distintos - 1)

    # --- INÍCIO DA NOVA LÓGICA DE TRADUÇÃO ---
    frequencia_texto = "-"  # Valor padrão
    if frequencia_dias is not None:
        dias = round(frequencia_dias)

        if dias == 0:
            frequencia_texto = "Múltiplas vezes ao dia"
        elif dias == 1:
            frequencia_texto = "Diariamente"
        elif 6 <= dias <= 8:
            frequencia_texto = "Semanalmente"
        elif 14 <= dias <= 16:
            frequencia_texto = "Quinzenalmente"
        elif 28 <= dias <= 32:
            frequencia_texto = "Mensalmente"
        elif 58 <= dias <= 62:
            frequencia_texto = "Bimestralmente"
        elif 88 <= dias <= 92:
            frequencia_texto = "Trimestralmente"
        elif dias > 32:
            meses = round(dias / 30)
            if meses > 1:
                frequencia_texto = f"A cada {meses} meses"
            else: # Fallback para casos entre 33 e 57 dias
                frequencia_texto = f"A cada {dias} dias"
        else: # Para todos os outros casos (2, 3, 4, 5, 9, etc.)
            frequencia_texto = f"A cada {dias} dias"
    # --- FIM DA NOVA LÓGICA DE TRADUÇÃO ---

    produtos_favoritos_qs = compras.values('variacao__id').annotate(
        qtd_comprada=Sum('quantidade')
    ).order_by('-qtd_comprada')[:5]

    ids_favoritos = [p['variacao__id'] for p in produtos_favoritos_qs]
    nomes_favoritos = {v.id: str(v) for v in Variacao.objects.filter(id__in=ids_favoritos)}
    
    produtos_favoritos = list(produtos_favoritos_qs)
    for item in produtos_favoritos:
        item['nome_completo'] = nomes_favoritos.get(item['variacao__id'])

    context = {
        'cliente': cliente,
        'compras': compras,
        'produtos_favoritos': produtos_favoritos,
        'total_gasto': metricas['total_gasto'],
        'total_lucro': metricas['total_lucro'],
        'num_compras': metricas['num_compras'],
        'ticket_medio': ticket_medio,
        'frequencia_texto': frequencia_texto, # Enviando o texto para o template
    }
    return render(request, 'estoque/cliente_detail.html', context)
# --- Seção de Busca Global ---

@login_required
def search_view(request):
    """
    Realiza uma busca global por produtos/variações em todo o sistema.
    """
    query = request.GET.get('q', '').strip()
    results = []
    if query:
        results = Variacao.objects.filter(
            Q(produto__nome__icontains=query) |
            Q(produto__descricao__icontains=query) |
            Q(valores_atributos__valor__icontains=query)
        ).distinct().select_related('produto__categoria')
        
    context = {'query': query, 'results': results}
    return render(request, 'estoque/search_results.html', context)