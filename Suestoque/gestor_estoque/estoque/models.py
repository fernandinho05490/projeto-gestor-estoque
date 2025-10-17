from django.db import models
from django.db.models import Sum, F
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

# --- Modelos de Atributos (sem alterações) ---
class Atributo(models.Model):
    nome = models.CharField(max_length=100, unique=True, help_text="Ex: Cor, Tamanho")
    def __str__(self): return self.nome

class ValorAtributo(models.Model):
    atributo = models.ForeignKey(Atributo, on_delete=models.CASCADE, related_name='valores')
    valor = models.CharField(max_length=100, help_text="Ex: Azul, P, 110v")
    class Meta: unique_together = ('atributo', 'valor')
    def __str__(self): return f"{self.atributo.nome}: {self.valor}"

# --- INÍCIO: NOVO MODELO DE CLIENTE ---
class Cliente(models.Model):
    nome = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, blank=True, unique=True, null=True)
    email = models.EmailField(blank=True, unique=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nome
# --- FIM: NOVO MODELO DE CLIENTE ---

# --- Modelos Principais (sem alterações) ---
class Fornecedor(models.Model):
    nome = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    tempo_entrega_dias = models.PositiveIntegerField(
        default=7, 
        help_text="Tempo médio de entrega do fornecedor em dias. Essencial para o cálculo de reposição."
    )
    def __str__(self): return self.nome

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    class Meta: verbose_name_plural = "Categorias"
    def __str__(self): return self.nome

class Produto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True)
    data_de_criacao = models.DateTimeField(auto_now_add=True)
    data_de_atualizacao = models.DateTimeField(auto_now=True)
    def __str__(self): return self.nome

class Variacao(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='variacoes')
    valores_atributos = models.ManyToManyField(ValorAtributo, related_name='variacoes')
    preco_de_custo = models.DecimalField(max_digits=10, decimal_places=2)
    preco_de_venda = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_em_estoque = models.PositiveIntegerField(default=0, editable=False)
    estoque_minimo = models.PositiveIntegerField(default=0, help_text="Estoque de segurança.")
    estoque_ideal = models.PositiveIntegerField(default=1)
    codigo_barras = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True, 
        help_text="Código de barras (EAN-13, etc.) da variação."
    )

    def __str__(self):
        valores = " | ".join([str(valor.valor) for valor in self.valores_atributos.all().order_by('atributo__nome')])
        return f"{self.produto.nome} ({valores})"
    
    @property
    def valor_total_em_estoque(self):
        if self.preco_de_custo is None: return 0
        return self.quantidade_em_estoque * self.preco_de_custo

    def get_status_estoque(self):
        if self.quantidade_em_estoque < self.estoque_minimo: return 'PERIGO'
        elif self.quantidade_em_estoque <= self.estoque_ideal: return 'ATENCAO'
        else: return 'OK'

class MovimentacaoEstoque(models.Model):
    TIPO_MOVIMENTACAO = (('ENTRADA', 'Entrada'), ('SAIDA', 'Saída'), ('AJUSTE', 'Ajuste'))
    variacao = models.ForeignKey(Variacao, on_delete=models.CASCADE, related_name='movimentacoes')
    quantidade = models.IntegerField()
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMENTACAO)
    data = models.DateTimeField(default=timezone.now)
    descricao = models.CharField(max_length=255, blank=True)
    
    # --- INÍCIO DA ALTERAÇÃO ---
    # Adiciona a ligação opcional a um cliente (para vendas)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='compras')
    # --- FIM DA ALTERAÇÃO ---

    def __str__(self): return f"{self.variacao} - {self.tipo}: {self.quantidade}"


# --- Modelos de Gestão de Compras (sem alterações) ---
class OrdemDeCompra(models.Model):
    STATUS_CHOICES = (
        ('PENDENTE', 'Pendente'),
        ('ENVIADA', 'Enviada ao Fornecedor'),
        ('RECEBIDA', 'Recebida'),
        ('CANCELADA', 'Cancelada'),
    )
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')

    class Meta:
        verbose_name = "Ordem de Compra"
        verbose_name_plural = "Ordens de Compra"

    def __str__(self):
        return f"Pedido #{self.id} - {self.fornecedor.nome}"

    def get_custo_total(self):
        total = self.itens.aggregate(total=Sum(F('quantidade') * F('custo_unitario')))['total']
        return total or 0
    get_custo_total.short_description = "Custo Total (R$)"

class ItemOrdemDeCompra(models.Model):
    ordem_de_compra = models.ForeignKey(OrdemDeCompra, on_delete=models.CASCADE, related_name='itens')
    variacao = models.ForeignKey(Variacao, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField()
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2, help_text="Custo do produto no momento da compra.")

    class Meta:
        verbose_name = "Item da Ordem de Compra"
        verbose_name_plural = "Itens da Ordem de Compra"
        unique_together = ('ordem_de_compra', 'variacao')

    def __str__(self):
        return f"{self.quantidade}x {self.variacao}"

    def get_subtotal(self):
        return self.quantidade * self.custo_unitario

class MetaVenda(models.Model):
    # Idealmente, cada meta estaria ligada a um usuário ou à empresa, mas vamos simplificar por agora.
    # Se quiser adicionar multi-usuário no futuro, basta adicionar:
    # usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    
    valor_meta = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        help_text="O valor da meta de faturamento para o mês."
    )
    mes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="O mês da meta (1 para Janeiro, 12 para Dezembro)."
    )
    ano = models.PositiveIntegerField(
        help_text="O ano da meta."
    )

    class Meta:
        verbose_name = "Meta de Venda"
        verbose_name_plural = "Metas de Vendas"
        # Garante que só exista uma meta por mês/ano.
        unique_together = ('mes', 'ano')

    def __str__(self):
        # Cria um nome legível, ex: "Meta para 10/2025"
        return f"Meta para {self.mes}/{self.ano}"