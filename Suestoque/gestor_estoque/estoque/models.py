from django.db import models
from django.db.models import Sum, F

class Fornecedor(models.Model):
    nome = models.CharField(max_length=200)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.nome

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.nome

class Produto(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True)
    
    preco_de_custo = models.DecimalField(max_digits=10, decimal_places=2, help_text="Preço pago pelo produto.")
    preco_de_venda = models.DecimalField(max_digits=10, decimal_places=2, help_text="Preço que o cliente final paga.")
    
    # O coração da lógica de estoque
    quantidade_em_estoque = models.PositiveIntegerField(default=0, editable=False, help_text="Quantidade atual no estoque. Atualizado por entradas/saídas.")
    estoque_minimo = models.PositiveIntegerField(default=0, help_text="A quantidade mínima para alertar a necessidade de compra.")
    estoque_ideal = models.PositiveIntegerField(default=1, help_text="A quantidade que você deseja ter em estoque após a reposição.")

    data_de_criacao = models.DateTimeField(auto_now_add=True)
    data_de_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome
        
    # Propriedades para facilitar cálculos e visualização no Admin
    @property
    def valor_total_em_estoque(self):
        """Calcula o valor total do item em estoque baseado no preço de custo."""
        # Se o preço de custo ainda não foi definido, o valor total é 0.
        if self.preco_de_custo is None:
            return 0
        return self.quantidade_em_estoque * self.preco_de_custo

    def get_status_estoque(self):
        """
        Retorna o status do estoque em texto para uso no template.
        PERIGO: Abaixo do mínimo.
        ATENCAO: Entre o mínimo e o ideal.
        OK: Acima do ideal.
        """
        if self.quantidade_em_estoque < self.estoque_minimo:
            return 'PERIGO'
    # Se não está abaixo do mínimo, checamos se está abaixo ou igual ao ideal.
        elif self.quantidade_em_estoque <= self.estoque_ideal:
            return 'ATENCAO'
    # Se não for nenhum dos anteriores, está tudo ok.
        else:
            return 'OK'


class MovimentacaoEstoque(models.Model):
    TIPO_MOVIMENTACAO = (
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
        ('AJUSTE', 'Ajuste'),
    )

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.IntegerField()
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMENTACAO)
    data = models.DateTimeField(auto_now_add=True)
    descricao = models.CharField(max_length=255, blank=True, help_text="Ex: 'Venda para cliente X' ou 'Compra do fornecedor Y'")

    def __str__(self):
        return f"{self.produto.nome} - {self.tipo}: {self.quantidade}"
