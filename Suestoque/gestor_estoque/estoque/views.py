# estoque/views.py

from django.db.models.functions import ExtractWeek, ExtractWeekDay,  ExtractHour
import json
from datetime import timedelta
from django.contrib import messages
from django.utils import timezone
from django.shortcuts import render, redirect
from django.db.models import Sum, F, Count
from datetime import datetime
from .models import Produto, MovimentacaoEstoque
from .forms import MovimentacaoForm
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
import urllib.parse


@login_required
def dashboard_estoque(request):
    # --- Lógica de Filtro (sem alterações) ---
    filtro_status = request.GET.get('filtro', None)
    produtos = Produto.objects.all().order_by('nome')
    if filtro_status == 'perigo':
        produtos = produtos.filter(quantidade_em_estoque__lt=F('estoque_minimo'))
    
    todos_os_produtos = Produto.objects.all()
    
    # --- Base de consulta para todas as vendas ---
    vendas = MovimentacaoEstoque.objects.filter(tipo='SAIDA')

    # --- INÍCIO: NOVOS CÁLCULOS FINANCEIROS POR PERÍODO ---

    # 1. Definir os períodos de tempo
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)

    # 2. Filtrar vendas por período
    vendas_no_mes = vendas.filter(data__date__gte=start_of_month)
    vendas_na_semana = vendas_no_mes.filter(data__date__gte=start_of_week)
    vendas_hoje = vendas_na_semana.filter(data__date=today)

    # 3. Função auxiliar para calcular faturamento e lucro (evita repetição)
    def calcular_metricas(queryset):
        faturamento = queryset.aggregate(
            total=Sum(F('quantidade') * F('produto__preco_de_venda'))
        )['total'] or 0
        custo = queryset.aggregate(
            total=Sum(F('quantidade') * F('produto__preco_de_custo'))
        )['total'] or 0
        lucro = faturamento - custo
        quantidade = queryset.aggregate(total=Sum('quantidade'))['total'] or 0
        return {'faturamento': faturamento, 'lucro': lucro, 'quantidade': quantidade}

    # 4. Calcular métricas para cada período
    metricas_hoje = calcular_metricas(vendas_hoje)
    metricas_semana = calcular_metricas(vendas_na_semana)
    metricas_mes = calcular_metricas(vendas_no_mes)
    metricas_total = calcular_metricas(vendas) # Reutilizando para o total

    # --- FIM: NOVOS CÁLCULOS FINANCEIROS POR PERÍODO ---

    # --- CÁLCULOS GERAIS E PARA GRÁFICOS (sem grandes alterações) ---
    total_inventory_value = todos_os_produtos.aggregate(
        total_value=Sum(F('quantidade_em_estoque') * F('preco_de_custo'))
    )['total_value'] or 0
    produtos_perigo_count = todos_os_produtos.filter(quantidade_em_estoque__lt=F('estoque_minimo')).count()
    ranking_lucro = vendas.values('produto__nome').annotate(
        lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')))
    ).order_by('-lucro')
    
    # (O código para os gráficos continua aqui, sem alterações...)
    produtos_mais_vendidos_qs = vendas.values('produto__nome').annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido')[:5]
    chart_mais_vendidos_labels = [item['produto__nome'] for item in produtos_mais_vendidos_qs]
    chart_mais_vendidos_data = [item['total_vendido'] for item in produtos_mais_vendidos_qs]
    valor_por_categoria_qs = todos_os_produtos.values('categoria__nome').annotate(valor_total=Sum(F('quantidade_em_estoque') * F('preco_de_custo'))).order_by('-valor_total')
    chart_valor_categoria_labels = [item['categoria__nome'] or 'Sem Categoria' for item in valor_por_categoria_qs]
    chart_valor_categoria_data = [float(item['valor_total'] or 0) for item in valor_por_categoria_qs]
    status_counts = {'OK': 0, 'ATENCAO': 0, 'PERIGO': 0}
    for produto in todos_os_produtos:
        status = produto.get_status_estoque()
        status_counts[status] += 1
    chart_status_labels = list(status_counts.keys())
    chart_status_data = list(status_counts.values())

    form_movimentacao = MovimentacaoForm()
    
    context = {
        # Dados da Tabela e Cards
        'produtos': produtos,
        'total_inventory_value': total_inventory_value,
        'produtos_perigo_count': produtos_perigo_count,
        'total_produtos': todos_os_produtos.count(),
        'filtro_status': filtro_status,
        'form_movimentacao': form_movimentacao,

        # Métricas Totais
        'faturamento_total': metricas_total['faturamento'],
        'lucro_total': metricas_total['lucro'],

        # Métricas por Período
        'metricas_hoje': metricas_hoje,
        'metricas_semana': metricas_semana,
        'metricas_mes': metricas_mes,

        # Rankings de Lucro
        'top_5_lucrativos': ranking_lucro[:5],
        'piores_5_lucrativos': ranking_lucro.order_by('lucro')[:5],

        # --- INÍCIO DA CORREÇÃO: DADOS DOS GRÁFICOS QUE FALTAVAM ---
        'chart_mais_vendidos_labels': json.dumps(chart_mais_vendidos_labels),
        'chart_mais_vendidos_data': json.dumps(chart_mais_vendidos_data),
        'chart_valor_categoria_labels': json.dumps(chart_valor_categoria_labels),
        'chart_valor_categoria_data': json.dumps(chart_valor_categoria_data),
        'chart_status_labels': json.dumps(chart_status_labels),
        'chart_status_data': json.dumps(chart_status_data),
        # --- FIM DA CORREÇÃO ---
    }
    return render(request, 'estoque/dashboard.html', context)

@login_required
@permission_required('estoque.add_movimentacaoestoque', raise_exception=True)
def registrar_movimentacao(request):
    if request.method == 'POST':
        form = MovimentacaoForm(request.POST)
        if form.is_valid():
            produto = form.cleaned_data['produto']
            quantidade = form.cleaned_data['quantidade']
            tipo = form.cleaned_data['tipo']
            descricao = form.cleaned_data['descricao']

            # --- INÍCIO DA VALIDAÇÃO DE ESTOQUE ---
            if tipo == 'SAIDA':
                if quantidade > produto.quantidade_em_estoque:
                    # Se a quantidade de saída for maior que o estoque, cria uma mensagem de erro
                    messages.error(request, f"Erro: A quantidade de saída ({quantidade}) é maior que o estoque atual ({produto.quantidade_em_estoque}) do produto '{produto.nome}'.")
                    # Interrompe a execução e redireciona de volta ao dashboard
                    return redirect('dashboard_estoque')
            # --- FIM DA VALIDAÇÃO DE ESTOQUE ---

            # Se a validação passar (ou se for uma ENTRADA), o código continua normalmente
            MovimentacaoEstoque.objects.create(
                produto=produto,
                quantidade=quantidade,
                tipo=tipo,
                descricao=descricao
            )
            messages.success(request, 'Movimentação registrada com sucesso!')
        else:
            # Pega o primeiro erro do formulário para uma mensagem mais específica
            error_field, error_list = next(iter(form.errors.items()))
            messages.error(request, f"Erro no campo '{error_field}': {error_list[0]}")
    
    return redirect('dashboard_estoque')

@login_required
@permission_required('estoque.change_produto', raise_exception=True)
def relatorio_vendas_view(request, periodo):
    today = timezone.now().date()
    dia_filtro = request.GET.get('dia')
    semana_filtro = request.GET.get('semana')

    periodo_titulo_original, periodo_titulo_detalhe = "", ""
    chart_titulo, chart_breakdown_labels, chart_breakdown_data = "", [], []
    chart_hourly_title, chart_hourly_labels, chart_hourly_data = "", [], []
    
    # Mapeamento dos dias da semana (sempre disponível para os títulos)
    dias_semana_map = {1: 'Domingo', 2: 'Segunda-feira', 3: 'Terça-feira', 4: 'Quarta-feira', 5: 'Quinta-feira', 6: 'Sexta-feira', 7: 'Sábado'}

    # Lógica para definir o período e gerar os dados do gráfico de detalhamento
    if periodo == 'semana':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        periodo_titulo_original = "Nesta Semana"
        
        if not dia_filtro:
            chart_titulo = "Desempenho Diário (Unidades)"
            vendas_diarias = MovimentacaoEstoque.objects.filter(tipo='SAIDA', data__date__range=[start_date, end_date]) \
                .annotate(dia_da_semana=ExtractWeekDay('data')).values('dia_da_semana') \
                .annotate(total_vendas=Sum('quantidade')).order_by('dia_da_semana')
            
            vendas_map = {item['dia_da_semana']: item['total_vendas'] for item in vendas_diarias}
            # SINTAXE CORRIGIDA: dia[:3] em vez de dia.[:3]
            chart_breakdown_labels = [dia[:3] for dia in dias_semana_map.values()] # Abreviado para o gráfico
            chart_breakdown_data = [vendas_map.get(i, 0) for i in range(1, 8)]

    elif periodo == 'mes':
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
        periodo_titulo_original = "Neste Mês"
        
        if not semana_filtro:
            chart_titulo = "Desempenho Semanal (Unidades)"
            vendas_semanais = MovimentacaoEstoque.objects.filter(tipo='SAIDA', data__date__range=[start_date, end_date]) \
                .annotate(semana_do_ano=ExtractWeek('data')).values('semana_do_ano') \
                .annotate(total_vendas=Sum('quantidade')).order_by('semana_do_ano')
            
            semana_inicial_mes = start_date.isocalendar()[1]
            for item in vendas_semanais:
                semana_no_mes = item['semana_do_ano'] - semana_inicial_mes + 1
                chart_breakdown_labels.append(f"Semana {semana_no_mes}")
                chart_breakdown_data.append(item['total_vendas'])
    else:
        start_date = today
        end_date = today
        periodo_titulo_original = "Hoje"

    # Lógica de filtro drill-down (aplicada sobre o período base)
    vendas_periodo = MovimentacaoEstoque.objects.filter(tipo='SAIDA', data__date__range=[start_date, end_date])
    
    if dia_filtro:
        dia_filtro_int = int(dia_filtro)
        vendas_periodo = vendas_periodo.filter(data__week_day=dia_filtro_int)
        periodo_titulo_detalhe = f" / {dias_semana_map.get(dia_filtro_int, '')}"

        # --- INÍCIO DA NOVA LÓGICA: GRÁFICO DE VENDAS POR HORA ---
        chart_hourly_title = "Vendas por Hora (Unidades)"
        vendas_por_hora = vendas_periodo.annotate(hora=ExtractHour('data')).values('hora') \
            .annotate(total_vendas=Sum('quantidade')).order_by('hora')
        
        # Prepara os dados para o gráfico, preenchendo as horas sem vendas com zero
        vendas_map = {item['hora']: item['total_vendas'] for item in vendas_por_hora}
        chart_hourly_labels = [f"{h}h" for h in range(24)]
        chart_hourly_data = [vendas_map.get(h, 0) for h in range(24)]
        # --- FIM DA NOVA LÓGICA ---
    
    elif semana_filtro:
        semana_filtro_int = int(semana_filtro)
        semana_ano_absoluta = start_date.isocalendar()[1] + semana_filtro_int - 1
        vendas_periodo = vendas_periodo.filter(data__week=semana_ano_absoluta)
        periodo_titulo_detalhe = f" / Semana {semana_filtro}"
    
    # Geração dos gráficos de detalhamento (só rodam se não houver filtro)
    if not (dia_filtro or semana_filtro):
        if periodo == 'semana':
            chart_titulo = "Desempenho Diário (Unidades)"
            # ... (código para gerar vendas_diarias) ...
            chart_breakdown_labels = [dia[:3] for dia in dias_semana_map.values()]
            # ... (código para preencher chart_breakdown_data) ...
        elif periodo == 'mes':
            chart_titulo = "Desempenho Semanal (Unidades)"
            # ... (código para gerar vendas_semanais e preencher os dados do gráfico) ...

    # Cálculos finais sobre o queryset (que pode estar filtrado ou não)
    vendas_detalhadas = vendas_periodo.values('produto__nome').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('produto__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')))
    ).order_by('-total_faturamento')
    
    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('produto__preco_de_venda'), default=0),
        lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')), default=0),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'vendas_detalhadas': vendas_detalhadas,
        'periodo_titulo': periodo_titulo_original,
        'periodo_titulo_detalhe': periodo_titulo_detalhe,
        'periodo': periodo,
        'totais_periodo': totais_periodo,
        'chart_titulo': chart_titulo,
        'chart_breakdown_labels': json.dumps(chart_breakdown_labels),
        'chart_breakdown_data': json.dumps(chart_breakdown_data),
        'filtro_ativo': bool(dia_filtro or semana_filtro),
        'chart_hourly_title': chart_hourly_title,
        'chart_hourly_labels': json.dumps(chart_hourly_labels),
        'chart_hourly_data': json.dumps(chart_hourly_data),
    }
    
    return render(request, 'estoque/relatorio_vendas.html', context)

# ADICIONE ESTA CLASSE NO FINAL DO ARQUIVO
class CustomLoginView(LoginView):
    template_name = 'estoque/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        # Se o usuário for um superusuário (admin), ele pode ser redirecionado
        # para o 'next' (página do admin) ou para o dashboard.
        if self.request.user.is_superuser:
            next_url = self.request.GET.get('next')
            if next_url:
                return next_url
            return reverse_lazy('dashboard_estoque')
        
        # Se for qualquer outro usuário (um Vendedor, por exemplo),
        # SEMPRE redirecione para o dashboard, ignorando o 'next'.
        else:
            return reverse_lazy('dashboard_estoque')

@login_required
@permission_required('estoque.change_produto', raise_exception=True)
def relatorios_view(request):
    # Pega as datas do formulário (via método GET)
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Inicializa as variáveis
    vendas_detalhadas = None
    totais_periodo = {'faturamento': 0, 'lucro': 0, 'quantidade': 0}

    # Verifica se as duas datas foram enviadas
    if start_date_str and end_date_str:
        try:
            # Converte as strings de data (dd/mm/YYYY) para objetos date
            start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
            end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()

            # Filtra as vendas no intervalo de datas selecionado
            vendas_periodo = MovimentacaoEstoque.objects.filter(
                tipo='SAIDA',
                data__date__range=[start_date, end_date]
            )

            # Agrupa por produto e calcula as métricas
            vendas_detalhadas = vendas_periodo.values('produto__nome').annotate(
                total_quantidade=Sum('quantidade'),
                total_faturamento=Sum(F('quantidade') * F('produto__preco_de_venda')),
                total_lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')))
            ).order_by('-total_faturamento')

            # Calcula os totais para os cards de resumo
            totais_periodo = vendas_periodo.aggregate(
                faturamento=Sum(F('quantidade') * F('produto__preco_de_venda'), default=0),
                lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')), default=0),
                quantidade=Sum('quantidade', default=0)
            )
        except (ValueError, TypeError):
            # Caso as datas estejam em formato inválido, ignora e não faz nada
            pass

    context = {
        'page_title': 'Relatórios Avançados',
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'start_date': start_date_str, # Envia as datas de volta para preencher o formulário
        'end_date': end_date_str,
    }
    return render(request, 'estoque/relatorios.html', context)

@login_required
@permission_required('estoque.change_produto', raise_exception=True)
def exportar_relatorio_pdf(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Pega as opções dos checkboxes
    incluir_graficos = request.GET.get('incluir_graficos') == 'on'
    incluir_ranking = request.GET.get('incluir_ranking') == 'on'

    if not (start_date_str and end_date_str):
        return HttpResponse("Período de datas não especificado.", status=400)

    start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
    end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
    periodo_titulo = f"de {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"

    vendas_periodo = MovimentacaoEstoque.objects.filter(tipo='SAIDA', data__date__range=[start_date, end_date])
    
    # --- Cálculos que sempre acontecem ---
    vendas_detalhadas = vendas_periodo.values('produto__nome').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('produto__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')))
    ).order_by('-total_faturamento')

    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('produto__preco_de_venda'), default=0),
        lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')), default=0),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'vendas_detalhadas': vendas_detalhadas,
        'totais_periodo': totais_periodo,
        'periodo_titulo': periodo_titulo,
        'incluir_graficos': incluir_graficos,
        'incluir_ranking': incluir_ranking,
    }

    # --- Cálculos condicionais (só se o usuário pediu) ---
    if incluir_ranking:
        ranking_lucro = vendas_periodo.values('produto__nome').annotate(
            lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')))
        ).order_by('-lucro')
        context['top_5_lucrativos'] = ranking_lucro[:5]

    if incluir_graficos:
        # Prepara dados para o gráfico de vendas
        produtos_mais_vendidos_qs = vendas_periodo.values('produto__nome') \
            .annotate(total_vendido=Sum('quantidade')).order_by('-total_vendido')[:5]
        
        # Configuração do gráfico para a API do QuickChart
        chart_config = {
            'type': 'bar',
            'data': {
                'labels': [item['produto__nome'] for item in produtos_mais_vendidos_qs],
                'datasets': [{
                    'label': 'Unidades Vendidas',
                    'data': [item['total_vendido'] for item in produtos_mais_vendidos_qs],
                    'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 1
                }]
            },
            'options': { 'indexAxis': 'y' }
        }
        # Codifica a configuração do gráfico para ser usada na URL
        encoded_chart = urllib.parse.quote(json.dumps(chart_config))
        context['chart_url'] = f'https://quickchart.io/chart?c={encoded_chart}'

    # --- Geração do PDF (continua igual) ---
    html_string = render_to_string('estoque/relatorio_pdf.html', context)
    pdf = HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_vendas_{start_date_str.replace("/", "-")}_a_{end_date_str.replace("/", "-")}.pdf"'
    
    return response