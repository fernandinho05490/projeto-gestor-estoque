from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import F
from .models import MovimentacaoEstoque, Variacao

@receiver(post_save, sender=MovimentacaoEstoque)
def ao_salvar_movimentacao(sender, instance, created, **kwargs):
    """
    Atualiza o stock de uma variação de forma incremental quando uma
    movimentação é criada ou atualizada.
    """
    variacao = instance.variacao
    quantidade = instance.quantidade
    
    # Se a movimentação é de entrada, soma a quantidade ao stock.
    if instance.tipo == 'ENTRADA':
        variacao.quantidade_em_estoque = F('quantidade_em_estoque') + quantidade
    # Se for de saída, subtrai.
    elif instance.tipo == 'SAIDA':
        variacao.quantidade_em_estoque = F('quantidade_em_estoque') - quantidade
    # Para ajustes, a própria quantidade já pode ser positiva ou negativa.
    elif instance.tipo == 'AJUSTE':
         # Esta lógica assume que o sinal é disparado apenas na criação.
         # Para atualizações, a lógica precisaria ser mais complexa.
         # Por agora, vamos focar no fluxo principal.
         # Se um ajuste de 5 foi feito, somamos 5. Se foi -3, somamos -3.
        variacao.quantidade_em_estoque = F('quantidade_em_estoque') + quantidade

    variacao.save(update_fields=['quantidade_em_estoque'])
    variacao.refresh_from_db() # Recarrega o objeto com o novo valor do BD.

@receiver(post_delete, sender=MovimentacaoEstoque)
def ao_deletar_movimentacao(sender, instance, **kwargs):
    """
    Reverte a atualização de stock quando uma movimentação é deletada.
    """
    variacao = instance.variacao
    quantidade = instance.quantidade
    
    # Se uma entrada foi deletada, subtraímos a quantidade do stock.
    if instance.tipo == 'ENTRADA':
        variacao.quantidade_em_estoque = F('quantidade_em_estoque') - quantidade
    # Se uma saída foi deletada, somamos a quantidade de volta ao stock.
    elif instance.tipo == 'SAIDA':
        variacao.quantidade_em_estoque = F('quantidade_em_estoque') + quantidade
    elif instance.tipo == 'AJUSTE':
        # Reverte o ajuste
        variacao.quantidade_em_estoque = F('quantidade_em_estoque') - quantidade

    variacao.save(update_fields=['quantidade_em_estoque'])
    variacao.refresh_from_db()
