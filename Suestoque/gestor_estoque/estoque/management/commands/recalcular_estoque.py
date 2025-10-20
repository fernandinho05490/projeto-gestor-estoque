# estoque/management/commands/recalcular_estoque.py

from django.core.management.base import BaseCommand
from django.db.models import Sum, F, Case, When, Value, IntegerField
from estoque.models import Variacao, MovimentacaoEstoque
import time

class Command(BaseCommand):
    help = 'Recalcula o campo quantidade_em_estoque de todas as Variações com base nas MovimentacoesEstoque.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Iniciando recálculo do estoque..."))
        start_time = time.time()

        variacoes_atualizadas = 0
        variacoes_totais = Variacao.objects.count()

        # Itera sobre todas as variações
        for i, variacao in enumerate(Variacao.objects.all()):
            # Calcula o saldo final baseado em todas as movimentações daquela variação
            saldo = MovimentacaoEstoque.objects.filter(variacao=variacao).aggregate(
                saldo_final=Sum(
                    Case(
                        When(tipo='ENTRADA', then=F('quantidade')),
                        When(tipo='SAIDA', then=-F('quantidade')),
                        When(tipo='AJUSTE', then=F('quantidade')), # Assume que AJUSTE já tem sinal correto
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                )
            )['saldo_final']

            # Garante que o saldo seja no mínimo 0
            saldo_final_calculado = saldo or 0

            # Atualiza o campo quantidade_em_estoque apenas se for diferente
            if variacao.quantidade_em_estoque != saldo_final_calculado:
                variacao.quantidade_em_estoque = saldo_final_calculado
                variacao.save(update_fields=['quantidade_em_estoque'])
                variacoes_atualizadas += 1
                # Mostra progresso a cada 50 variações
                if (i + 1) % 50 == 0:
                     self.stdout.write(f"Processado {i + 1}/{variacoes_totais} variações...")


        end_time = time.time()
        duration = end_time - start_time

        self.stdout.write(self.style.SUCCESS(
            f"Recálculo concluído em {duration:.2f} segundos."
        ))
        if variacoes_atualizadas > 0:
            self.stdout.write(self.style.SUCCESS(
                f"{variacoes_atualizadas} variações tiveram o estoque corrigido."
            ))
        else:
             self.stdout.write(self.style.NOTICE(
                "Nenhuma variação precisou ter o estoque corrigido. Tudo certo!"
            ))