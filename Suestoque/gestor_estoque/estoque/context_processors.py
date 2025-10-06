from .models import Variacao, ItemOrdemDeCompra
from django.db.models import F

def notifications_processor(request):
    """
    Este processador de contexto verifica se há notificações de estoque
    e as disponibiliza para todos os templates.
    """
    # Apenas executa a lógica para usuários logados com permissão
    if request.user.is_authenticated and request.user.has_perm('estoque.change_variacao'):
        
        # --- INÍCIO DA LÓGICA INTELIGENTE ---
        # 1. Pega os IDs de todas as variações que já estão
        #    em uma ordem de compra com status 'PENDENTE' ou 'ENVIADA'.
        variacoes_em_pedidos_abertos = ItemOrdemDeCompra.objects.filter(
            ordem_de_compra__status__in=['PENDENTE', 'ENVIADA']
        ).values_list('variacao_id', flat=True)

        # 2. Busca todas as variações que estão com estoque em PERIGO,
        #    mas EXCLUI aquelas que já foram encontradas no passo anterior.
        variacoes_em_alerta = Variacao.objects.filter(
            quantidade_em_estoque__lt=F('estoque_minimo')
        ).exclude(
            id__in=variacoes_em_pedidos_abertos
        ).select_related('produto')
        # --- FIM DA LÓGICA INTELIGENTE ---

        return {
            'notificacoes_alerta': variacoes_em_alerta,
            'notificacoes_contagem': variacoes_em_alerta.count()
        }
    
    # Se o usuário não tiver permissão, retorna um dicionário vazio
    return {}

