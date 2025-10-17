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
try:
    from weasyprint import HTML
    WEASYPRINT_DISPONIVEL = True
except (OSError, ImportError):
    WEASYPRINT_DISPONIVEL = False

# Módulos Locais da Aplicação
from .forms import MovimentacaoForm
from .models import MovimentacaoEstoque, OrdemDeCompra, ItemOrdemDeCompra, Variacao, Cliente, MetaVenda

# --- Constantes ---
TIPO_SAIDA = 'SAIDA'
TIPO_ENTRADA = 'ENTRADA'


# --- Seção de Autenticação ---

class CustomLoginView(LoginView):
    """
    View de login customizada.
    """
    template_name = 'estoque/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_superuser:
            next_url = self.request.GET.get('next')
            if next_url:
                return next_url
        return reverse_lazy('dashboard_estoque')


# --- Seção do Dashboard e Views Principais ---

@login_required
def dashboard_estoque(request):
    """
    Exibe a página inicial com as informações mais importantes e acionáveis:
    Metas, Desempenho por Período e Tabela de Estoque.
    """
    # --- LÓGICA DE METAS ---
    today = timezone.now()
    mes_atual = today.month
    ano_atual = today.year

    meta_venda = MetaVenda.objects.filter(mes=mes_atual, ano=ano_atual).first()
    progresso_percentual = 0
    faturamento_mes_atual = Decimal('0')
    mensagem_motivacional = ""

    start_of_month = today.date().replace(day=1)
    vendas_mes_qs = MovimentacaoEstoque.objects.filter(tipo=TIPO_SAIDA, data__date__gte=start_of_month)
    metricas_mes = vendas_mes_qs.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        quantidade=Sum('quantidade', default=0)
    )
    faturamento_mes_atual = metricas_mes['faturamento']

    if meta_venda and meta_venda.valor_meta > 0:
        progresso_percentual = min(round((faturamento_mes_atual / meta_venda.valor_meta) * 100), 100)
        
        if progresso_percentual >= 100:
            mensagem_motivacional = "Parabéns! Você bateu a sua meta este mês! 🏆"
        elif progresso_percentual > 75:
            mensagem_motivacional = "Você está quase lá! Falta pouco para bater a meta!"
        elif progresso_percentual > 50:
            mensagem_motivacional = "Você já passou da metade do caminho. Continue assim!"
        else:
            mensagem_motivacional = "Um ótimo começo de mês! Continue focado."
    
    # --- LÓGICA PARA O DASHBOARD (ENXUTA) ---
    filtro_status = request.GET.get('filtro', None)
    todas_as_variacoes = Variacao.objects.select_related('produto__categoria').all()
    
    if filtro_status == 'perigo':
        variacoes_list = [v for v in todas_as_variacoes if v.get_status_estoque() == 'PERIGO']
    else:
        variacoes_list = list(todas_as_variacoes.order_by('produto__nome'))

    vendas_qs = MovimentacaoEstoque.objects.filter(tipo=TIPO_SAIDA)

    start_of_week = today.date() - timedelta(days=today.date().weekday())
    
    metricas_hoje = vendas_qs.filter(data__date=today.date()).aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        quantidade=Sum('quantidade', default=0)
    )
    metricas_semana = vendas_qs.filter(data__date__gte=start_of_week).aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'meta_venda': meta_venda,
        'faturamento_mes_atual': faturamento_mes_atual,
        'progresso_percentual': progresso_percentual,
        'mensagem_motivacional': mensagem_motivacional,
        'variacoes': variacoes_list,
        'filtro_status': filtro_status,
        'form_movimentacao': MovimentacaoForm(),
        'metricas_hoje': metricas_hoje,
        'metricas_semana': metricas_semana,
        'metricas_mes': metricas_mes,
    }
    
    return render(request, 'estoque/dashboard.html', context)


@login_required
@require_POST
@permission_required('estoque.add_movimentacaoestoque', raise_exception=True)
def registrar_movimentacao(request):
    """ Processa o formulário de registro de movimentação de estoque. """
    form = MovimentacaoForm(request.POST)
    if form.is_valid():
        variacao = form.cleaned_data['variacao']
        quantidade = form.cleaned_data['quantidade']
        tipo = form.cleaned_data['tipo']
        
        if tipo == TIPO_SAIDA and quantidade > variacao.quantidade_em_estoque:
            messages.error(request, f"Estoque insuficiente para '{variacao}'. Disponível: {variacao.quantidade_em_estoque}")
        else:
            form.save()
            messages.success(request, 'Movimentação registrada com sucesso!')
    else:
        erros = '. '.join([f'{field}: {error[0]}' for field, error in form.errors.items()])
        messages.error(request, f'Erro ao registrar. Verifique os dados. {erros}')
        
    return redirect('dashboard_estoque')


# --- Seção de Análises Detalhadas ---

@login_required
def analises_view(request):
    """ Exibe a página de análises detalhadas com todos os gráficos e rankings. """
    vendas_qs = MovimentacaoEstoque.objects.filter(tipo=TIPO_SAIDA)
    todas_as_variacoes = Variacao.objects.select_related('produto__categoria').all()

    # --- LÓGICA DO RESUMO GERAL (MOVIDA DO DASHBOARD) ---
    metricas_globais = vendas_qs.aggregate(
        faturamento_total=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro_total=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0'))
    )

    inventario_info = todas_as_variacoes.aggregate(
        valor_total=Sum(F('quantidade_em_estoque') * F('preco_de_custo'), default=Decimal('0'))
    )
    
    produtos_perigo_count = sum(1 for v in todas_as_variacoes if v.get_status_estoque() == 'PERIGO')
    
    # --- LÓGICA DOS GRÁFICOS E RANKINGS ---
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
    
    # Rankings de Lucratividade
    ranking_lucro_qs = vendas_qs.values('variacao__id').annotate(
        lucro_gerado=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-lucro_gerado')
    top_5_lucrativos = list(ranking_lucro_qs[:5])
    piores_5_lucrativos = list(ranking_lucro_qs.order_by('lucro_gerado')[:5])
    ids_ranking = [item['variacao__id'] for item in top_5_lucrativos + piores_5_lucrativos]
    variacoes_ranking = {v.id: str(v) for v in Variacao.objects.filter(id__in=ids_ranking)}
    for item in top_5_lucrativos:
        item['nome_completo'] = variacoes_ranking.get(item['variacao__id'], 'N/A')
    for item in piores_5_lucrativos:
        item['nome_completo'] = variacoes_ranking.get(item['variacao__id'], 'N/A')

    context = {
        'faturamento_total': metricas_globais['faturamento_total'],
        'lucro_total': metricas_globais['lucro_total'],
        'total_inventory_value': inventario_info['valor_total'],
        'produtos_perigo_count': produtos_perigo_count,
        'total_produtos': todas_as_variacoes.count(),
        'top_5_lucrativos': top_5_lucrativos,
        'piores_5_lucrativos': piores_5_lucrativos,
        'chart_mais_vendidos_labels': json.dumps(chart_mais_vendidos_labels),
        'chart_mais_vendidos_data': json.dumps(chart_mais_vendidos_data),
        'chart_valor_categoria_labels': json.dumps(chart_valor_categoria_labels),
        'chart_valor_categoria_data': json.dumps(chart_valor_categoria_data),
        'chart_status_labels': json.dumps(chart_status_labels),
        'chart_status_data': json.dumps(chart_status_data),
    }

    return render(request, 'estoque/analises.html', context)


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
    Exibe um relatório de vendas detalhado para um período específico.
    """
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
    
    vendas_periodo = MovimentacaoEstoque.objects.filter(
        tipo=TIPO_SAIDA, 
        data__date__range=[start_date, end_date]
    ).select_related('variacao__produto')

    filtro_ativo = bool(dia_filtro or semana_filtro)
    periodo_titulo_detalhe = ""
    dias_semana_map = {1: 'Domingo', 2: 'Segunda', 3: 'Terça', 4: 'Quarta', 5: 'Quinta', 6: 'Sexta', 7: 'Sábado'}

    if dia_filtro and dia_filtro.isdigit():
        vendas_periodo = vendas_periodo.filter(data__week_day=int(dia_filtro))
        periodo_titulo_detalhe = f" / {dias_semana_map.get(int(dia_filtro), '')}"
    
    if semana_filtro and semana_filtro.isdigit():
        semana_ano_absoluta = start_date.isocalendar()[1] + int(semana_filtro) - 1
        vendas_periodo = vendas_periodo.filter(data__week=semana_ano_absoluta)
        periodo_titulo_detalhe = f" / Semana {semana_filtro}"
    
    vendas_detalhadas_qs = vendas_periodo.values('variacao__id').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-total_faturamento')
    
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

    produto_mais_vendido_info = vendas_periodo.values('variacao__id').annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido').first()
    produto_mais_vendido = None
    if produto_mais_vendido_info:
        produto_mais_vendido = Variacao.objects.get(id=produto_mais_vendido_info['variacao__id'])
        produto_mais_vendido.total_vendido = produto_mais_vendido_info['total_vendido']

    produto_mais_lucrativo_info = vendas_periodo.values('variacao__id').annotate(lucro_gerado=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))).order_by('-lucro_gerado').first()
    produto_mais_lucrativo = None
    if produto_mais_lucrativo_info:
        produto_mais_lucrativo = Variacao.objects.get(id=produto_mais_lucrativo_info['variacao__id'])
        produto_mais_lucrativo.lucro_gerado = produto_mais_lucrativo_info['lucro_gerado']

    is_daily_view = (periodo == 'hoje' or dia_filtro)
    
    context = {
        'periodo': periodo,
        'periodo_titulo': periodo_titulo,
        'periodo_titulo_detalhe': periodo_titulo_detalhe,
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'is_daily_view': is_daily_view,
        'filtro_ativo': filtro_ativo,
        'produto_mais_vendido': produto_mais_vendido,
        'produto_mais_lucrativo': produto_mais_lucrativo,
    }

    if is_daily_view:
        vendas_por_hora = vendas_periodo.annotate(hora=ExtractHour('data')).values('hora').annotate(total=Sum('quantidade')).order_by('hora')
        vendas_map = {item['hora']: item['total'] for item in vendas_por_hora}
        context['chart_hourly_labels'] = json.dumps([f"{h}h" for h in range(24)])
        context['chart_hourly_data'] = json.dumps([vendas_map.get(h, 0) for h in range(24)])
    else:
        if periodo == 'semana' or semana_filtro:
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

        ranking_lucro = vendas_detalhadas_qs.order_by('-total_lucro')[:5]
        lucro_labels = [nomes_variacoes.get(item['variacao__id'], 'N/A') for item in ranking_lucro]
        lucro_data = [float(item['total_lucro']) for item in ranking_lucro]
        context['chart_lucro_labels'] = json.dumps(lucro_labels)
        context['chart_lucro_data'] = json.dumps(lucro_data)
        context['chart_lucro_title'] = "Top 5 Produtos por Lucro"

    return render(request, 'estoque/relatorio_vendas.html', context)


@login_required
@permission_required('estoque.view_movimentacaoestoque', raise_exception=True)
def exportar_relatorio_pdf(request):
    """ Gera e exporta um relatório de vendas em formato PDF. """
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

    vendas_periodo = MovimentacaoEstoque.objects.filter(
        tipo=TIPO_SAIDA, data__date__range=[start_date, end_date]
    )

    vendas_detalhadas_qs = vendas_periodo.values('variacao__id').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-total_faturamento')

    ids_vendas = [item['variacao__id'] for item in vendas_detalhadas_qs]
    nomes_variacoes = Variacao.objects.in_bulk(ids_vendas)
    
    vendas_detalhadas = list(vendas_detalhadas_qs)
    for item in vendas_detalhadas:
        variacao_obj = nomes_variacoes.get(item['variacao__id'])
        item['nome_completo'] = str(variacao_obj) if variacao_obj else "N/A"

    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0')),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'periodo_titulo': f"de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
        'incluir_graficos': request.GET.get('incluir_graficos') == 'on',
        'incluir_ranking': request.GET.get('incluir_ranking') == 'on',
    }

    html_string = render_to_string('estoque/relatorio_pdf.html', context)
    pdf_file = HTML(string=html_string).write_pdf()
    
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_vendas_{start_date}_{end_date}.pdf"'
    
    return response


# --- Seção de Gestão de Compras ---

@login_required
@permission_required('estoque.add_ordemdecompra', raise_exception=True)
def compras_view(request):
    """ Analisa o estoque para sugerir itens para reposição. """
    periodo_analise_dias = 30
    data_inicio_analise = timezone.now() - timedelta(days=periodo_analise_dias)

    variacoes_em_pedidos_abertos_ids = ItemOrdemDeCompra.objects.filter(
        ordem_de_compra__status__in=['PENDENTE', 'ENVIADA']
    ).values_list('variacao_id', flat=True)

    vendas_no_periodo = MovimentacaoEstoque.objects.filter(
        tipo=TIPO_SAIDA, 
        data__gte=data_inicio_analise
    ).values('variacao_id').annotate(total_vendido=Sum('quantidade'))

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
        
        demanda_no_prazo = venda_media * tempo_entrega
        ponto_de_pedido = demanda_no_prazo + variacao.estoque_minimo

        if variacao.quantidade_em_estoque <= ponto_de_pedido:
            variacao.media_vendas_diaria = round(venda_media, 2)
            variacao.dias_de_estoque_restante = int(variacao.quantidade_em_estoque / venda_media) if venda_media > 0 else float('inf')
            variacao.ponto_de_pedido = int(ponto_de_pedido)
            variacao.quantidade_a_comprar = max(0, variacao.estoque_ideal - variacao.quantidade_em_estoque)
            variacoes_para_repor.append(variacao)

    context = {'variacoes_para_repor': variacoes_para_repor}
    return render(request, 'estoque/compras.html', context)


@login_required
@require_POST
@transaction.atomic
@permission_required('estoque.add_ordemdecompra', raise_exception=True)
def gerar_ordem_de_compra(request):
    """ Gera ordens de compra agrupadas por fornecedor. """
    variacao_ids = request.POST.getlist('variacao_id')
    if not variacao_ids:
        messages.error(request, "Nenhum item foi selecionado.")
        return redirect('compras')
    
    variacoes_selecionadas = Variacao.objects.filter(id__in=variacao_ids).select_related('produto__fornecedor')
    
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
    """Lista todas as ordens de compra."""
    ordens = OrdemDeCompra.objects.select_related('fornecedor').order_by('-data_criacao')
    context = {'ordens': ordens}
    return render(request, 'estoque/ordem_compra_list.html', context)


@login_required
@permission_required('estoque.view_ordemdecompra', raise_exception=True)
def ordem_compra_detail_view(request, pk):
    """Exibe os detalhes de uma ordem de compra."""
    ordem = get_object_or_404(OrdemDeCompra, pk=pk)
    itens = ordem.itens.select_related('variacao__produto')
    context = {'ordem': ordem, 'itens': itens}
    return render(request, 'estoque/ordem_compra_detail.html', context)


@login_required
@require_POST
@transaction.atomic
@permission_required('estoque.change_ordemdecompra', raise_exception=True)
def ordem_compra_receber_view(request, pk):
    """ Marca uma ordem de compra como 'RECEBIDA' e atualiza o estoque. """
    ordem = get_object_or_404(OrdemDeCompra, pk=pk)
    
    if ordem.status not in ['RECEBIDA', 'CANCELADA']:
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
    """Renderiza a interface do PDV."""
    return render(request, 'estoque/pdv.html', {})


@login_required
def search_variacoes_pdv(request):
    """ Endpoint de API para a busca de produtos no PDV. """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    results = Variacao.objects.filter(
        Q(produto__nome__icontains=query) | 
        Q(valores_atributos__valor__icontains=query) |
        Q(codigo_barras__iexact=query)
    ).distinct().select_related('produto')[:10]

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
    """ Endpoint de API para a busca de clientes no PDV. """
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
@transaction.atomic
def finalizar_venda_pdv(request):
    """ Endpoint de API para finalizar a venda do PDV. """
    try:
        data = json.loads(request.body)
        cart = data.get('cart')
        cliente_id = data.get('clienteId')

        if not cart:
            return JsonResponse({'status': 'error', 'message': 'O carrinho está vazio.'}, status=400)

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

        cliente_instancia = None
        if cliente_id:
            cliente_instancia = get_object_or_404(Cliente, id=cliente_id)

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
        return JsonResponse({'status': 'error', 'message': f'Ocorreu um erro inesperado: {str(e)}'}, status=500)


# --- Seção de Gestão de Clientes (CRM) ---

@login_required
@permission_required('estoque.view_cliente')
def cliente_list_view(request):
    """ Exibe a lista de clientes e rankings com filtros por período. """
    periodo_selecionado = request.GET.get('periodo', 'total')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    today = timezone.now().date()
    start_date, end_date = None, None
    periodo_titulo = "Todo o Período"

    if periodo_selecionado == 'hoje':
        start_date = end_date = today
        periodo_titulo = "Hoje"
    elif periodo_selecionado == 'semana':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        periodo_titulo = "Nesta Semana"
    elif periodo_selecionado == 'mes':
        start_date = today.replace(day=1)
        end_date = today
        periodo_titulo = "Neste Mês"
    elif start_date_str and end_date_str:
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%d/%m/%Y').date()
            end_date = timezone.datetime.strptime(end_date_str, '%d/%m/%Y').date()
            periodo_titulo = f"de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
            periodo_selecionado = 'custom'
        except ValueError:
            messages.error(request, "Formato de data inválido. Use DD/MM/AAAA.")
            start_date, end_date = None, None
            periodo_selecionado = 'total'
    
    vendas_base = MovimentacaoEstoque.objects.filter(tipo=TIPO_SAIDA, cliente__isnull=False)
    
    if start_date and end_date:
        vendas_base = vendas_base.filter(data__date__range=[start_date, end_date])

    top_gastadores = vendas_base.values('cliente__id', 'cliente__nome').annotate(total_gasto=Sum(F('quantidade') * F('variacao__preco_de_venda'))).filter(total_gasto__gt=0).order_by('-total_gasto')[:10]

    mais_frequentes = vendas_base.annotate(dia_compra=TruncDate('data')).values('cliente__id', 'cliente__nome').annotate(num_compras=Count('dia_compra', distinct=True)).filter(num_compras__gt=0).order_by('-num_compras')[:10]
    
    context = {
        'clientes': Cliente.objects.all().order_by('nome'),
        'top_gastadores': top_gastadores,
        'mais_frequentes': mais_frequentes,
        'periodo_selecionado': periodo_selecionado,
        'periodo_titulo': periodo_titulo,
        'start_date_value': start_date_str or '',
        'end_date_value': end_date_str or '',
    }
    return render(request, 'estoque/cliente_list.html', context)


@login_required
@permission_required('estoque.view_cliente')
def cliente_detail_view(request, pk):
    """ Exibe um dashboard detalhado para um cliente específico. """
    cliente = get_object_or_404(Cliente, pk=pk)
    
    compras = cliente.compras.order_by('-data').select_related('variacao__produto')

    compras_agrupadas = []
    if compras:
        transacoes = defaultdict(list)
        primeira_compra_grupo = compras[0]
        for compra in compras:
            if (primeira_compra_grupo.data - compra.data).total_seconds() < 2:
                transacoes[primeira_compra_grupo.id].append(compra)
            else:
                primeira_compra_grupo = compra
                transacoes[primeira_compra_grupo.id].append(compra)

        for id_transacao, itens in transacoes.items():
            total_itens = sum(item.quantidade for item in itens)
            total_valor = sum(item.quantidade * item.variacao.preco_de_venda for item in itens)
            
            compras_agrupadas.append({
                'data': itens[0].data,
                'total_itens': total_itens,
                'total_valor': total_valor,
                'itens': itens,
            })

    metricas = compras.aggregate(
        total_gasto=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=Decimal('0')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=Decimal('0'))
    )

    ticket_medio = metricas['total_gasto'] / len(compras_agrupadas) if compras_agrupadas else 0
    num_compras = len(compras_agrupadas)

    frequencia_dias = None
    if len(compras_agrupadas) > 1:
        datas_unicas = sorted(list(set(c['data'].date() for c in compras_agrupadas)))
        if len(datas_unicas) > 1:
            duracao_total = (datas_unicas[-1] - datas_unicas[0]).days
            frequencia_dias = duracao_total / (len(datas_unicas) - 1) if duracao_total > 0 else 1

    frequencia_texto = "-"
    if frequencia_dias is not None:
        dias = round(frequencia_dias)
        if dias <= 1: frequencia_texto = "Diariamente"
        elif 6 <= dias <= 8: frequencia_texto = "Semanalmente"
        else: frequencia_texto = f"A cada {dias} dias"

    produtos_favoritos_qs = compras.values('variacao__id').annotate(qtd_comprada=Sum('quantidade')).order_by('-qtd_comprada')[:5]
    ids_favoritos = [p['variacao__id'] for p in produtos_favoritos_qs]
    nomes_favoritos = {v.id: str(v) for v in Variacao.objects.filter(id__in=ids_favoritos)}
    
    produtos_favoritos = list(produtos_favoritos_qs)
    for item in produtos_favoritos:
        item['nome_completo'] = nomes_favoritos.get(item['variacao__id'])

    context = {
        'cliente': cliente,
        'compras_agrupadas': compras_agrupadas,
        'produtos_favoritos': produtos_favoritos,
        'total_gasto': metricas['total_gasto'],
        'total_lucro': metricas['total_lucro'],
        'num_compras': num_compras,
        'ticket_medio': ticket_medio,
        'frequencia_texto': frequencia_texto,
    }
    return render(request, 'estoque/cliente_detail.html', context)


# --- Seção de Busca Global ---

@login_required
def search_view(request):
    """ Realiza uma busca global por produtos/variações. """
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