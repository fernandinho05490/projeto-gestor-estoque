import json
from datetime import datetime, timedelta
from urllib.parse import quote
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.db.models import F, Q, Sum
from django.db.models.functions import ExtractHour, ExtractWeek, ExtractWeekDay
from django.http import HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from weasyprint import HTML

from .forms import MovimentacaoForm
from .models import MovimentacaoEstoque, OrdemDeCompra, ItemOrdemDeCompra, Variacao


# --- Views de Autenticação (sem alterações) ---
class CustomLoginView(LoginView):
    template_name = 'estoque/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        if self.request.user.is_superuser:
            next_url = self.request.GET.get('next')
            if next_url:
                return next_url
            return reverse_lazy('dashboard_estoque')
        else:
            return reverse_lazy('dashboard_estoque')


# --- Views Principais (Dashboard e Movimentação) ---
@login_required
def dashboard_estoque(request):
    filtro_status = request.GET.get('filtro', None)
    
    variacoes = Variacao.objects.select_related('produto__categoria').order_by('produto__nome')

    if filtro_status == 'perigo':
        variacoes_list = [v for v in variacoes if v.get_status_estoque() == 'PERIGO']
    else:
        variacoes_list = list(variacoes)

    todas_as_variacoes = Variacao.objects.all()
    vendas = MovimentacaoEstoque.objects.filter(tipo='SAIDA')
    
    total_inventory_value = sum(v.valor_total_em_estoque for v in todas_as_variacoes if v.valor_total_em_estoque is not None)
    variacoes_perigo_count = sum(1 for v in todas_as_variacoes if v.get_status_estoque() == 'PERIGO')
    
    metricas_total = vendas.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=0),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=0)
    )
    
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    def calcular_metricas(queryset):
        return queryset.aggregate(
            faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=0),
            lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=0),
            quantidade=Sum('quantidade', default=0)
        )

    metricas_hoje = calcular_metricas(vendas.filter(data__date=today))
    metricas_semana = calcular_metricas(vendas.filter(data__date__gte=start_of_week))
    metricas_mes = calcular_metricas(vendas.filter(data__date__gte=start_of_month))

    mais_vendidas_qs = vendas.values('variacao__id').annotate(
        total_vendido=Sum('quantidade')
    ).order_by('-total_vendido')[:5]
    
    nomes_mais_vendidas = {item['variacao__id']: str(Variacao.objects.get(id=item['variacao__id'])) for item in mais_vendidas_qs}
    chart_mais_vendidos_labels = [nomes_mais_vendidas[item['variacao__id']] for item in mais_vendidas_qs]
    chart_mais_vendidos_data = [item['total_vendido'] for item in mais_vendidas_qs]

    valor_por_categoria_qs = Variacao.objects.values('produto__categoria__nome').annotate(
        valor_total=Sum(F('quantidade_em_estoque') * F('preco_de_custo'))
    ).order_by('-valor_total')
    chart_valor_categoria_labels = [item['produto__categoria__nome'] or 'Sem Categoria' for item in valor_por_categoria_qs]
    chart_valor_categoria_data = [float(item['valor_total'] or 0) for item in valor_por_categoria_qs]

    status_counts = {'OK': 0, 'ATENCAO': 0, 'PERIGO': 0}
    for v in todas_as_variacoes:
        status = v.get_status_estoque()
        status_counts[status] += 1
    chart_status_labels = list(status_counts.keys())
    chart_status_data = list(status_counts.values())

    ranking_lucro = vendas.values('variacao__id').annotate(
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-lucro')
    
    top_5_lucrativos = list(ranking_lucro[:5])
    piores_5_lucrativos = list(ranking_lucro.order_by('lucro')[:5])
    for item in top_5_lucrativos: item['nome_completo'] = str(Variacao.objects.get(id=item['variacao__id']))
    for item in piores_5_lucrativos: item['nome_completo'] = str(Variacao.objects.get(id=item['variacao__id']))

    form_movimentacao = MovimentacaoForm()

    context = {
        'variacoes': variacoes_list,
        'filtro_status': filtro_status,
        'form_movimentacao': form_movimentacao,
        'total_produtos': todas_as_variacoes.count(),
        'produtos_perigo_count': variacoes_perigo_count,
        'total_inventory_value': total_inventory_value,
        'faturamento_total': metricas_total['faturamento'],
        'lucro_total': metricas_total['lucro'],
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
@permission_required('estoque.add_movimentacaoestoque', raise_exception=True)
def registrar_movimentacao(request):
    if request.method == 'POST':
        form = MovimentacaoForm(request.POST)
        if form.is_valid():
            variacao = form.cleaned_data['variacao']
            quantidade = form.cleaned_data['quantidade']
            tipo = form.cleaned_data['tipo']
            
            if tipo == 'SAIDA' and quantidade > variacao.quantidade_em_estoque:
                messages.error(request, f"Estoque insuficiente para '{variacao}'. Disponível: {variacao.quantidade_em_estoque}")
                return redirect('dashboard_estoque')

            MovimentacaoEstoque.objects.create(
                variacao=variacao,
                quantidade=quantidade,
                tipo=tipo,
                descricao=form.cleaned_data['descricao']
            )
            messages.success(request, 'Movimentação registrada com sucesso!')
        else:
            messages.error(request, 'Erro ao registrar. Verifique os dados.')
    return redirect('dashboard_estoque')


# --- VIEWS DE RELATÓRIOS (RECONSTRUÍDAS) ---
@login_required
@permission_required('estoque.change_variacao', raise_exception=True)
def relatorios_view(request):
    context = {'page_title': 'Relatórios Avançados'}
    return render(request, 'estoque/relatorios.html', context)


@login_required
@permission_required('estoque.change_variacao', raise_exception=True)
def relatorio_vendas_view(request, periodo):
    today = timezone.now().date()
    dia_filtro = request.GET.get('dia')
    semana_filtro = request.GET.get('semana')

    is_daily_view = (periodo == 'hoje' or dia_filtro)

    context = {
        'periodo': periodo,
        'filtro_ativo': bool(dia_filtro or semana_filtro),
        'is_daily_view': is_daily_view,
        'periodo_titulo_detalhe': ""
    }

    if periodo == 'semana':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        context['periodo_titulo'] = "Nesta Semana"
    elif periodo == 'mes':
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        context['periodo_titulo'] = "Neste Mês"
    elif periodo == 'hoje':
        start_date, end_date = today, today
        context['periodo_titulo'] = "Hoje"
    else:
        return redirect('dashboard_estoque')

    vendas_periodo = MovimentacaoEstoque.objects.filter(tipo='SAIDA', data__date__range=[start_date, end_date])
    
    dias_semana_map = {1: 'Domingo', 2: 'Segunda', 3: 'Terça', 4: 'Quarta', 5: 'Quinta', 6: 'Sexta', 7: 'Sábado'}
    if dia_filtro:
        dia_filtro_int = int(dia_filtro)
        vendas_periodo = vendas_periodo.filter(data__week_day=dia_filtro_int)
        context['periodo_titulo_detalhe'] = f" / {dias_semana_map.get(dia_filtro_int, '')}"
    
    if semana_filtro:
        semana_filtro_int = int(semana_filtro)
        semana_ano_absoluta = start_date.isocalendar()[1] + semana_filtro_int - 1
        vendas_periodo = vendas_periodo.filter(data__week=semana_ano_absoluta)
        context['periodo_titulo_detalhe'] = f" / Semana {semana_filtro}"

    if is_daily_view:
        context['chart_hourly_title'] = "Vendas por Hora (Unidades)"
        vendas_por_hora = vendas_periodo.annotate(hora=ExtractHour('data')).values('hora').annotate(total=Sum('quantidade')).order_by('hora')
        vendas_map = {item['hora']: item['total'] for item in vendas_por_hora}
        context['chart_hourly_labels'] = json.dumps([f"{h}h" for h in range(24)])
        context['chart_hourly_data'] = json.dumps([vendas_map.get(h, 0) for h in range(24)])
        
        if vendas_periodo.exists():
            produto_mais_vendido = vendas_periodo.values('variacao__id').annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido').first()
            produto_mais_lucrativo = vendas_periodo.values('variacao__id').annotate(lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))).order_by('-lucro').first()
            if produto_mais_vendido:
                produto_mais_vendido['nome_completo'] = str(Variacao.objects.get(id=produto_mais_vendido['variacao__id']))
                context['produto_mais_vendido'] = produto_mais_vendido
            if produto_mais_lucrativo:
                produto_mais_lucrativo['nome_completo'] = str(Variacao.objects.get(id=produto_mais_lucrativo['variacao__id']))
                context['produto_mais_lucrativo'] = produto_mais_lucrativo
    else:
        context['chart_lucro_title'] = "Top 5 Variações Mais Lucrativas (R$)"
        ranking_lucro_periodo = vendas_periodo.values('variacao__id').annotate(lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))).order_by('-lucro')[:5]
        for item in ranking_lucro_periodo: item['nome_completo'] = str(Variacao.objects.get(id=item['variacao__id']))
        context['chart_lucro_labels'] = json.dumps([item['nome_completo'] for item in ranking_lucro_periodo])
        context['chart_lucro_data'] = json.dumps([float(item['lucro']) for item in ranking_lucro_periodo])

        if periodo == 'semana':
            context['chart_titulo'] = "Desempenho Diário (Unidades)"
            vendas_diarias = vendas_periodo.annotate(dia=ExtractWeekDay('data')).values('dia').annotate(total=Sum('quantidade')).order_by('dia')
            vendas_map = {item['dia']: item['total'] for item in vendas_diarias}
            context['chart_breakdown_labels'] = json.dumps([dia[:3] for dia in dias_semana_map.values()])
            context['chart_breakdown_data'] = json.dumps([vendas_map.get(i, 0) for i in range(1, 8)])
        elif periodo == 'mes':
            context['chart_titulo'] = "Desempenho Semanal (Unidades)"
            vendas_semanais = vendas_periodo.annotate(semana=ExtractWeek('data')).values('semana').annotate(total=Sum('quantidade')).order_by('semana')
            semana_inicial_mes = start_date.isocalendar()[1]
            labels, data = [], []
            for item in vendas_semanais:
                semana_no_mes = item['semana'] - semana_inicial_mes + 1
                labels.append(f"Semana {semana_no_mes}")
                data.append(item['total'])
            context['chart_breakdown_labels'] = json.dumps(labels)
            context['chart_breakdown_data'] = json.dumps(data)

    vendas_detalhadas = vendas_periodo.values('variacao__id').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-total_faturamento')
    for item in vendas_detalhadas: item['nome_completo'] = str(Variacao.objects.get(id=item['variacao__id']))
    
    context['vendas_detalhadas'] = vendas_detalhadas
    context['totais_periodo'] = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=0),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=0),
        quantidade=Sum('quantidade', default=0)
    )
    
    return render(request, 'estoque/relatorio_vendas.html', context)


@login_required
@permission_required('estoque.change_variacao', raise_exception=True)
def exportar_relatorio_pdf(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    incluir_graficos = request.GET.get('incluir_graficos') == 'on'
    incluir_ranking = request.GET.get('incluir_ranking') == 'on'

    if not (start_date_str and end_date_str):
        messages.error(request, "Por favor, selecione um período de datas válido.")
        return redirect('relatorios')

    start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
    end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
    periodo_titulo = f"de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"

    vendas_periodo = MovimentacaoEstoque.objects.filter(tipo='SAIDA', data__date__range=[start_date, end_date])
    
    vendas_detalhadas = vendas_periodo.values('variacao__id').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
    ).order_by('-total_faturamento')
    for item in vendas_detalhadas: item['nome_completo'] = str(Variacao.objects.get(id=item['variacao__id']))

    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('variacao__preco_de_venda'), default=0),
        lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')), default=0),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'periodo_titulo': periodo_titulo,
        'incluir_graficos': incluir_graficos,
        'incluir_ranking': incluir_ranking,
    }

    if incluir_ranking:
        ranking_lucro = vendas_periodo.values('variacao__id').annotate(
            lucro=Sum(F('quantidade') * (F('variacao__preco_de_venda') - F('variacao__preco_de_custo')))
        ).order_by('-lucro')[:5]
        for item in ranking_lucro: item['nome_completo'] = str(Variacao.objects.get(id=item['variacao__id']))
        context['ranking_lucratividade'] = ranking_lucro

    if incluir_graficos:
        mais_vendidas_qs = vendas_periodo.values('variacao__id').annotate(
            total_vendido=Sum('quantidade')).order_by('-total_vendido')[:5]
        nomes_mais_vendidas = {item['variacao__id']: str(Variacao.objects.get(id=item['variacao__id'])) for item in mais_vendidas_qs}
        
        chart_config = {
            'type': 'horizontalBar',
            'data': {
                'labels': [nomes_mais_vendidas.get(item['variacao__id']) for item in mais_vendidas_qs],
                'datasets': [{
                    'label': 'Unidades Vendidas',
                    'data': [item['total_vendido'] for item in mais_vendidas_qs],
                    'backgroundColor': 'rgba(0, 122, 255, 0.7)',
                    'borderColor': 'rgba(0, 122, 255, 1)',
                    'borderWidth': 1,
                    'borderRadius': 5,
                }]
            },
            'options': {
                'responsive': True,
                'legend': {'display': False},
                'scales': {
                    'xAxes': [{'ticks': {'beginAtZero': True, 'precision': 0, 'fontFamily': 'Inter', 'fontColor': '#666'}, 'gridLines': { 'drawBorder': False, 'color': 'rgba(0, 0, 0, 0.05)' }}],
                    'yAxes': [{'ticks': {'fontFamily': 'Inter', 'fontColor': '#333', 'fontSize': 10}, 'gridLines': {'display': False}}]
                },
                'plugins': { 'datalabels': { 'anchor': 'end', 'align': 'right', 'offset': 8, 'color': '#1d1d1f', 'font': { 'family': 'Inter', 'weight': '600' } } },
                'layout': { 'padding': {'left': 10, 'right': 30, 'top': 10, 'bottom': 10} }
            }
        }
        context['chart_url'] = f'https://quickchart.io/chart?c={quote(json.dumps(chart_config))}'

    html_string = render_to_string('estoque/relatorio_pdf.html', context)
    pdf = HTML(string=html_string).write_pdf()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_vendas.pdf"'
    
    return response



@login_required
def search_view(request):
    query = request.GET.get('q', '')
    results = []

    if query:
        # A busca é feita em múltiplos campos para ser mais eficaz
        results = Variacao.objects.filter(
            Q(produto__nome__icontains=query) |
            Q(produto__descricao__icontains=query) |
            Q(valores_atributos__valor__icontains=query)
        ).distinct().select_related('produto__categoria')

    context = {
        'query': query,
        'results': results,
    }
    return render(request, 'estoque/search_results.html', context)


# --- VIEWS DE COMPRAS ATUALIZADAS E CORRIGIDAS ---

@login_required
@permission_required('estoque.add_ordemdecompra', raise_exception=True)
def compras_view(request):
    # 1. Primeiro, pegamos os IDs de todas as variações que já estão
    #    em uma ordem de compra com status 'PENDENTE' ou 'ENVIADA'.
    variacoes_em_pedidos_abertos = ItemOrdemDeCompra.objects.filter(
        ordem_de_compra__status__in=['PENDENTE', 'ENVIADA']
    ).values_list('variacao_id', flat=True)

    # 2. Agora, a consulta principal busca por variações que precisam de reposição,
    #    MAS EXCLUI aquelas que já encontramos no passo anterior.
    variacoes_para_repor = Variacao.objects.filter(
        quantidade_em_estoque__lt=F('estoque_minimo')
    ).exclude(
        id__in=variacoes_em_pedidos_abertos
    ).select_related('produto__fornecedor').order_by('produto__fornecedor', 'produto__nome')

    # O resto da view continua igual
    for variacao in variacoes_para_repor:
        variacao.quantidade_a_comprar = variacao.estoque_ideal - variacao.quantidade_em_estoque

    context = {
        'variacoes_para_repor': variacoes_para_repor,
    }
    return render(request, 'estoque/compras.html', context)


@login_required
@permission_required('estoque.add_ordemdecompra', raise_exception=True)
def gerar_ordem_de_compra(request):
    if request.method == 'POST':
        variacao_ids = request.POST.getlist('variacao_id')
        
        if not variacao_ids:
            messages.error(request, "Nenhum item foi selecionado para gerar a ordem de compra.")
            return redirect('compras')

        variacoes_por_fornecedor = defaultdict(list)
        variacoes_selecionadas = Variacao.objects.filter(id__in=variacao_ids).select_related('produto__fornecedor')
        
        for variacao in variacoes_selecionadas:
            if variacao.produto.fornecedor:
                variacoes_por_fornecedor[variacao.produto.fornecedor].append(variacao)
            else:
                pass
        
        ordens_criadas = 0
        for fornecedor, variacoes in variacoes_por_fornecedor.items():
            ordem = OrdemDeCompra.objects.create(fornecedor=fornecedor, status='PENDENTE')
            
            for variacao in variacoes:
                quantidade_sugerida = variacao.estoque_ideal - variacao.quantidade_em_estoque
                ItemOrdemDeCompra.objects.create(
                    ordem_de_compra=ordem,
                    variacao=variacao,
                    quantidade=quantidade_sugerida,
                    custo_unitario=variacao.preco_de_custo
                )
            ordens_criadas += 1
        
        if ordens_criadas > 0:
            messages.success(request, f"{ordens_criadas} ordem(ns) de compra gerada(s) com sucesso!")
        else:
            messages.warning(request, "Não foi possível gerar ordens de compra. Verifique se os produtos selecionados têm um fornecedor associado.")

    return redirect('compras')


# --- VIEWS PARA VISUALIZAÇÃO DE ORDENS DE COMPRA ---

@login_required
@permission_required('estoque.view_ordemdecompra', raise_exception=True)
def ordem_compra_list_view(request):
    ordens = OrdemDeCompra.objects.all().select_related('fornecedor').order_by('-data_criacao')
    context = {
        'ordens': ordens
    }
    return render(request, 'estoque/ordem_compra_list.html', context)

@login_required
@permission_required('estoque.view_ordemdecompra', raise_exception=True)
def ordem_compra_detail_view(request, pk):
    ordem = get_object_or_404(OrdemDeCompra, pk=pk)
    itens = ordem.itens.all().select_related('variacao__produto')
    context = {
        'ordem': ordem,
        'itens': itens
    }
    return render(request, 'estoque/ordem_compra_detail.html', context)

@login_required
@permission_required('estoque.change_ordemdecompra', raise_exception=True)
def ordem_compra_receber_view(request, pk):
    if request.method == 'POST':
        ordem = get_object_or_404(OrdemDeCompra, pk=pk)
        
        if ordem.status != 'RECEBIDA' and ordem.status != 'CANCELADA':
            for item in ordem.itens.all():
                MovimentacaoEstoque.objects.create(
                    variacao=item.variacao,
                    quantidade=item.quantidade,
                    tipo='ENTRADA',
                    descricao=f"Entrada referente ao Pedido de Compra #{ordem.id}"
                )
            
            ordem.status = 'RECEBIDA'
            ordem.data_recebimento = timezone.now()
            ordem.save()
            messages.success(request, f"Pedido #{ordem.id} marcado como recebido e estoque atualizado com sucesso!")
        else:
            messages.warning(request, f"Este pedido já foi processado ou cancelado.")
            
    return redirect('ordem_compra_detail', pk=pk)


