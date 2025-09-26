# estoque/forms.py 

from django import forms
from .models import Produto, MovimentacaoEstoque

class MovimentacaoForm(forms.Form):
    produto = forms.ModelChoiceField(
        queryset=Produto.objects.all().order_by('nome'),
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