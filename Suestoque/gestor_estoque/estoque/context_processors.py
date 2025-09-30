from .models import Variacao

def notifications_processor(request):
    """
    Este processador de contexto verifica se há notificações de estoque
    e as disponibiliza para todos os templates.
    """
    if request.user.is_authenticated and request.user.has_perm('estoque.change_variacao'):
        # Busca todas as variações que estão abaixo do estoque mínimo
        variacoes_em_alerta = [
            v for v in Variacao.objects.select_related('produto').all() 
            if v.get_status_estoque() == 'PERIGO'
        ]
        
        return {
            'notificacoes_alerta': variacoes_em_alerta,
            'notificacoes_contagem': len(variacoes_em_alerta)
        }
    
    return {}
