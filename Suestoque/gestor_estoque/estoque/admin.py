from django.contrib import admin
from django.db.models import Sum, F
from .models import Produto, Categoria, Fornecedor, MovimentacaoEstoque

# Para registrar MovimentacaoEstoque como uma linha dentro de Produto
class MovimentacaoEstoqueInline(admin.TabularInline):
    model = MovimentacaoEstoque
    extra = 1  # Quantos formulários extras para adicionar
    readonly_fields = ('data',) # A data é automática
    
@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'quantidade_em_estoque', 'estoque_minimo', 'status_do_estoque', 'valor_total_item')
    list_filter = ('categoria', 'fornecedor')
    search_fields = ('nome', 'descricao')
    readonly_fields = ('quantidade_em_estoque', 'valor_total_item') # Esses campos são calculados
    inlines = [MovimentacaoEstoqueInline] # Mostra as movimentações na página do produto

    # --- INÍCIO DA ALTERAÇÃO ---
    # A função abaixo foi reescrita para usar o novo método do models.py
    # e o decorador @admin.display, que é a forma mais moderna de configurar a coluna.
    @admin.display(description="Status do Estoque")
    def status_do_estoque(self, obj):
        status = obj.get_status_estoque()
        if status == 'PERIGO':
            return "🔴 Repor Urgente"
        elif status == 'ATENCAO':
            return "🟡 Atenção"
        else: # 'OK'
            return "✅ OK"

    @admin.display(description="Valor Total (Custo)")
    def valor_total_item(self, obj):
        return f"R$ {obj.valor_total_em_estoque:.2f}"
    # --- FIM DA ALTERAÇÃO ---

    # Adicionando uma Ação para calcular o valor total do inventário
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Valor total do inventário
        total_inventory_value = Produto.objects.aggregate(
            total_value=Sum(F('quantidade_em_estoque') * F('preco_de_custo'))
        )['total_value'] or 0
        
        # Custo para reabastecer
        produtos_para_repor = Produto.objects.filter(quantidade_em_estoque__lt=F('estoque_ideal'))
        custo_total_reposicao = sum(
            (p.estoque_ideal - p.quantidade_em_estoque) * p.preco_de_custo for p in produtos_para_repor
        )

        extra_context['total_inventory_value'] = f"R$ {total_inventory_value:.2f}"
        extra_context['custo_total_reposicao'] = f"R$ {custo_total_reposicao:.2f}"
        
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ('produto', 'tipo', 'quantidade', 'data', 'descricao')
    list_filter = ('tipo', 'data')
    search_fields = ('produto__nome', 'descricao')
    autocomplete_fields = ['produto']

# Registros simples para Categoria e Fornecedor
admin.site.register(Categoria)
admin.site.register(Fornecedor)