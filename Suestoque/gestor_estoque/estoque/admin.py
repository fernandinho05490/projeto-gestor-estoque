from django.contrib import admin
from .models import (
    Atributo, ValorAtributo, Fornecedor, Categoria, 
    Produto, Variacao, MovimentacaoEstoque,
    OrdemDeCompra, ItemOrdemDeCompra
)

# --- Configurações para Atributos ---
class ValorAtributoInline(admin.TabularInline):
    model = ValorAtributo
    extra = 1

@admin.register(Atributo)
class AtributoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    inlines = [ValorAtributoInline]

@admin.register(ValorAtributo)
class ValorAtributoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'atributo')
    list_filter = ('atributo',)
    search_fields = ('valor', 'atributo__nome')


# --- Configurações para Produtos e Variações ---
class VariacaoInline(admin.TabularInline):
    model = Variacao
    extra = 1
    filter_horizontal = ('valores_atributos',)
    readonly_fields = ('quantidade_em_estoque',)
    autocomplete_fields = ('valores_atributos',)

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'categoria', 'fornecedor')
    list_filter = ('categoria', 'fornecedor')
    search_fields = ('nome', 'descricao')
    inlines = [VariacaoInline]

@admin.register(Variacao)
class VariacaoAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'produto', 'preco_de_venda', 'quantidade_em_estoque', 'status_do_estoque')
    list_filter = ('produto__categoria', 'valores_atributos')
    search_fields = ('produto__nome', 'valores_atributos__valor')
    autocomplete_fields = ('produto', 'valores_atributos')
    readonly_fields = ('quantidade_em_estoque',)

    @admin.display(description="Status do Estoque")
    def status_do_estoque(self, obj):
        status = obj.get_status_estoque()
        if status == 'PERIGO':
            return "🔴 Repor Urgente"
        elif status == 'ATENCAO':
            return "🟡 Atenção"
        else:
            return "✅ OK"

# --- Configurações para Movimentação de Estoque ---
@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = ('variacao', 'tipo', 'quantidade', 'data')
    list_filter = ('tipo', 'data', 'variacao__produto__categoria')
    search_fields = ('variacao__produto__nome', 'variacao__valores_atributos__valor', 'descricao')
    autocomplete_fields = ['variacao']


# --- INÍCIO: NOVAS CONFIGURAÇÕES PARA GESTÃO DE COMPRAS ---

class ItemOrdemDeCompraInline(admin.TabularInline):
    model = ItemOrdemDeCompra
    extra = 1
    autocomplete_fields = ('variacao',)
    
    # Preenche o campo de custo automaticamente com o valor da variação
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields['custo_unitario'].widget.attrs['readonly'] = 'readonly'
        return formset

@admin.register(OrdemDeCompra)
class OrdemDeCompraAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'data_criacao', 'get_custo_total')
    list_filter = ('status', 'fornecedor', 'data_criacao')
    date_hierarchy = 'data_criacao'
    autocomplete_fields = ('fornecedor',)
    inlines = [ItemOrdemDeCompraInline]
    readonly_fields = ('data_recebimento',)

# --- FIM: NOVAS CONFIGURAÇÕES ---


# --- Registros Simples ---
@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    search_fields = ('nome',)

admin.site.register(Categoria)

