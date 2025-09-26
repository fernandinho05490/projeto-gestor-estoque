# estoque/signals.py (VERSÃO CORRIGIDA)

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum  # <-- ESTA LINHA ESTAVA FALTANDO
from .models import MovimentacaoEstoque, Produto

def atualizar_estoque_produto(instance):
    """
    Função para recalcular o estoque de um produto com base em todas as suas movimentações.
    """
    produto = instance.produto
    
    # Calcula a soma de todas as movimentações para o produto específico
    # Usamos um único aggregate para ser mais eficiente
    movimentacoes = MovimentacaoEstoque.objects.filter(produto=produto).values('tipo').annotate(total=Sum('quantidade'))
    
    # Zera os contadores
    total_entradas = 0
    total_saidas = 0
    total_ajustes = 0

    # Itera sobre os resultados agregados
    for m in movimentacoes:
        if m['tipo'] == 'ENTRADA':
            total_entradas = m['total'] or 0
        elif m['tipo'] == 'SAIDA':
            total_saidas = m['total'] or 0
        elif m['tipo'] == 'AJUSTE':
            total_ajustes = m['total'] or 0

    # Calcula o estoque final
    estoque_atualizado = total_entradas - total_saidas + total_ajustes
    
    # Atualiza o campo no modelo Produto e salva
    # Usamos update em vez de save() para evitar loop de signals, se houver outros
    Produto.objects.filter(pk=produto.pk).update(quantidade_em_estoque=estoque_atualizado)


@receiver(post_save, sender=MovimentacaoEstoque)
def ao_salvar_movimentacao(sender, instance, created, **kwargs):
    """
    Este sinal é chamado toda vez que uma MovimentacaoEstoque é salva (criada ou atualizada).
    """
    atualizar_estoque_produto(instance)


@receiver(post_delete, sender=MovimentacaoEstoque)
def ao_deletar_movimentacao(sender, instance, **kwargs):
    """
    Este sinal é chamado toda vez que uma MovimentacaoEstoque é deletada.
    """
    atualizar_estoque_produto(instance)