from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from .models import MovimentacaoEstoque, Variacao

# A FUNÇÃO AGORA ATUALIZA O ESTOQUE DA VARIAÇÃO
def atualizar_estoque_variacao(instance):
    variacao = instance.variacao
    
    movimentacoes = MovimentacaoEstoque.objects.filter(variacao=variacao).values('tipo').annotate(total=Sum('quantidade'))
    
    total_entradas, total_saidas, total_ajustes = 0, 0, 0

    for m in movimentacoes:
        if m['tipo'] == 'ENTRADA': total_entradas = m['total'] or 0
        elif m['tipo'] == 'SAIDA': total_saidas = m['total'] or 0
        elif m['tipo'] == 'AJUSTE': total_ajustes = m['total'] or 0

    estoque_atualizado = total_entradas - total_saidas + total_ajustes
    
    Variacao.objects.filter(pk=variacao.pk).update(quantidade_em_estoque=estoque_atualizado)

@receiver(post_save, sender=MovimentacaoEstoque)
def ao_salvar_movimentacao(sender, instance, created, **kwargs):
    atualizar_estoque_variacao(instance)

@receiver(post_delete, sender=MovimentacaoEstoque)
def ao_deletar_movimentacao(sender, instance, **kwargs):
    atualizar_estoque_variacao(instance)