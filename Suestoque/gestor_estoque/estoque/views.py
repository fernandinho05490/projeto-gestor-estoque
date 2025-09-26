# estoque/views.py

import json
from datetime import timedelta
from django.contrib import messages
from django.utils import timezone
from django.shortcuts import render, redirect
from django.db.models import Sum, F, Count
from .models import Produto, MovimentacaoEstoque
from .forms import MovimentacaoForm
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

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
    periodo_titulo = ""
    
    # Define o período de tempo com base no parâmetro da URL
    if periodo == 'hoje':
        start_date = today
        periodo_titulo = "Hoje"
    elif periodo == 'semana':
        start_date = today - timedelta(days=today.weekday())
        periodo_titulo = "Nesta Semana"
    elif periodo == 'mes':
        start_date = today.replace(day=1)
        periodo_titulo = "Neste Mês"
    else:
        # Se o período for inválido, redireciona para o dashboard
        return redirect('dashboard_estoque')

    # Filtra as vendas do período
    vendas_periodo = MovimentacaoEstoque.objects.filter(
        tipo='SAIDA', 
        data__date__gte=start_date
    )

    # Agrupa por produto e calcula as métricas detalhadas
    vendas_detalhadas = vendas_periodo.values('produto__nome').annotate(
        total_quantidade=Sum('quantidade'),
        total_faturamento=Sum(F('quantidade') * F('produto__preco_de_venda')),
        total_lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')))
    ).order_by('-total_lucro')

    # Calcula os totais para os cards de resumo da página
    totais_periodo = vendas_periodo.aggregate(
        faturamento=Sum(F('quantidade') * F('produto__preco_de_venda'), default=0),
        lucro=Sum(F('quantidade') * (F('produto__preco_de_venda') - F('produto__preco_de_custo')), default=0),
        quantidade=Sum('quantidade', default=0)
    )

    context = {
        'vendas_detalhadas': vendas_detalhadas,
        'periodo_titulo': periodo_titulo,
        'totais_periodo': totais_periodo
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