from django import forms
from .models import Variacao

class MovimentacaoForm(forms.Form):
    # O CAMPO AGORA É UMA ESCOLHA DE VARIAÇÃO
    variacao = forms.ModelChoiceField(
        queryset=Variacao.objects.all().select_related('produto').order_by('produto__nome'),
        label="Produto (Variação)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantidade = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 10'})
    )
    tipo = forms.ChoiceField(
        choices=[('ENTRADA', 'Entrada'), ('SAIDA', 'Saída')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    descricao = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional (Ex: Venda para cliente X)'})
    )