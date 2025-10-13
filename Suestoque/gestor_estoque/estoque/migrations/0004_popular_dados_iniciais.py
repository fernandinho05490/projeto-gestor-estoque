from django.db import migrations
from django.utils import timezone
from datetime import date, time, timedelta, datetime # <-- LINHA CORRIGIDA
import random

def popular_dados_iniciais(apps, schema_editor):
    # Usamos apps.get_model para obter os modelos da versão histórica correta.
    Fornecedor = apps.get_model('estoque', 'Fornecedor')
    Categoria = apps.get_model('estoque', 'Categoria')
    Atributo = apps.get_model('estoque', 'Atributo')
    ValorAtributo = apps.get_model('estoque', 'ValorAtributo')
    Produto = apps.get_model('estoque', 'Produto')
    Variacao = apps.get_model('estoque', 'Variacao')
    MovimentacaoEstoque = apps.get_model('estoque', 'MovimentacaoEstoque')

    # --- LIMPEZA DE DADOS ANTIGOS (para tornar o script re-executável) ---
    MovimentacaoEstoque.objects.all().delete()
    Variacao.objects.all().delete()
    Produto.objects.all().delete()
    ValorAtributo.objects.all().delete()
    Atributo.objects.all().delete()
    Categoria.objects.all().delete()
    Fornecedor.objects.all().delete()

    # --- PASSO 1: Criar Fornecedores ---
    f_malhas, _ = Fornecedor.objects.get_or_create(nome="Malhas & Cia Premium", defaults={'tempo_entrega_dias': 15})
    f_denim, _ = Fornecedor.objects.get_or_create(nome="Urban Denim Co.", defaults={'tempo_entrega_dias': 20})
    f_moletom, _ = Fornecedor.objects.get_or_create(nome="Moletom Conforto", defaults={'tempo_entrega_dias': 10})
    f_acessorios, _ = Fornecedor.objects.get_or_create(nome="Acessórios Style", defaults={'tempo_entrega_dias': 5})
    f_casual, _ = Fornecedor.objects.get_or_create(nome="Casual Wear Solutions", defaults={'tempo_entrega_dias': 12})

    # --- PASSO 2: Criar Categorias ---
    cat_camisetas, _ = Categoria.objects.get_or_create(nome="Camisetas")
    cat_calcas, _ = Categoria.objects.get_or_create(nome="Calças")
    cat_casacos, _ = Categoria.objects.get_or_create(nome="Casacos")
    cat_acessorios, _ = Categoria.objects.get_or_create(nome="Acessórios")
    cat_bermudas, _ = Categoria.objects.get_or_create(nome="Bermudas")
    cat_vestidos, _ = Categoria.objects.get_or_create(nome="Vestidos")

    # --- PASSO 3: Criar Atributos e Valores ---
    attr_tamanho, _ = Atributo.objects.get_or_create(nome="Tamanho")
    t_p, _ = ValorAtributo.objects.get_or_create(atributo=attr_tamanho, valor="P")
    t_m, _ = ValorAtributo.objects.get_or_create(atributo=attr_tamanho, valor="M")
    t_g, _ = ValorAtributo.objects.get_or_create(atributo=attr_tamanho, valor="G")
    t_gg, _ = ValorAtributo.objects.get_or_create(atributo=attr_tamanho, valor="GG")
    t_unico, _ = ValorAtributo.objects.get_or_create(atributo=attr_tamanho, valor="Único")

    attr_cor, _ = Atributo.objects.get_or_create(nome="Cor")
    c_preto, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Preto")
    c_branco, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Branco")
    c_azul, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Azul Marinho")
    c_cinza, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Cinza Mescla")
    c_verde, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Verde Militar")
    c_vermelho, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Vermelho")
    c_bege, _ = ValorAtributo.objects.get_or_create(atributo=attr_cor, valor="Bege")

    attr_genero, _ = Atributo.objects.get_or_create(nome="Gênero")
    g_masc, _ = ValorAtributo.objects.get_or_create(atributo=attr_genero, valor="Masculino")
    g_fem, _ = ValorAtributo.objects.get_or_create(atributo=attr_genero, valor="Feminino")
    g_uni, _ = ValorAtributo.objects.get_or_create(atributo=attr_genero, valor="Unissex")

    # --- PASSO 4: Criar um Catálogo Extenso de Produtos e Variações ---
    produtos_data = [
        {"nome": "Camiseta Gola Careca Essencial", "cat": cat_camisetas, "forn": f_malhas, "vars": [
            {"vals": [c_preto, t_m, g_uni], "custo": 28, "venda": 69.9, "min": 10, "ideal": 50},
            {"vals": [c_branco, t_g, g_uni], "custo": 28, "venda": 69.9, "min": 10, "ideal": 40},
        ]},
        {"nome": "Calça Jeans Slim Fit", "cat": cat_calcas, "forn": f_denim, "vars": [
            {"vals": [c_azul, t_m, g_masc], "custo": 80, "venda": 189.9, "min": 5, "ideal": 15},
            {"vals": [c_preto, t_g, g_masc], "custo": 85, "venda": 199.9, "min": 5, "ideal": 12},
        ]},
        {"nome": "Moletom Canguru", "cat": cat_casacos, "forn": f_moletom, "vars": [
            {"vals": [c_cinza, t_g, g_uni], "custo": 90, "venda": 249.9, "min": 4, "ideal": 10},
            {"vals": [c_preto, t_m, g_uni], "custo": 90, "venda": 249.9, "min": 4, "ideal": 10},
        ]},
        {"nome": "Bermuda Chino", "cat": cat_bermudas, "forn": f_casual, "vars": [
            {"vals": [c_bege, t_m, g_masc], "custo": 55, "venda": 129.9, "min": 8, "ideal": 20},
        ]},
        {"nome": "Vestido Midi Canelado", "cat": cat_vestidos, "forn": f_malhas, "vars": [
            {"vals": [c_preto, t_p, g_fem], "custo": 75, "venda": 179.9, "min": 6, "ideal": 15},
        ]},
        {"nome": "Camiseta Polo Piquet", "cat": cat_camisetas, "forn": f_malhas, "vars": [
            {"vals": [c_azul, t_g, g_masc], "custo": 45, "venda": 119.9, "min": 7, "ideal": 25},
        ]},
        {"nome": "Jaqueta Jeans Clássica", "cat": cat_casacos, "forn": f_denim, "vars": [
            {"vals": [c_azul, t_m, g_uni], "custo": 110, "venda": 299.9, "min": 3, "ideal": 8},
        ]},
        {"nome": "Boné Trucker", "cat": cat_acessorios, "forn": f_acessorios, "vars": [
            {"vals": [c_preto, t_unico, g_uni], "custo": 20, "venda": 49.9, "min": 15, "ideal": 40},
        ]},
        {"nome": "Calça Cargo", "cat": cat_calcas, "forn": f_casual, "vars": [
            {"vals": [c_verde, t_g, g_masc], "custo": 95, "venda": 229.9, "min": 5, "ideal": 12},
        ]},
        {"nome": "Blusa de Tricô", "cat": cat_casacos, "forn": f_malhas, "vars": [
            {"vals": [c_bege, t_m, g_fem], "custo": 65, "venda": 159.9, "min": 6, "ideal": 18},
        ]},
        {"nome": "Camiseta Estampada Vintage", "cat": cat_camisetas, "forn": f_malhas, "vars": [
            {"vals": [c_branco, t_p, g_uni], "custo": 35, "venda": 89.9, "min": 8, "ideal": 25},
        ]},
        {"nome": "Cinto de Couro", "cat": cat_acessorios, "forn": f_acessorios, "vars": [
            {"vals": [c_preto, t_unico, g_uni], "custo": 40, "venda": 99.9, "min": 10, "ideal": 30},
        ]},
        {"nome": "Saia Jeans Mini", "cat": cat_calcas, "forn": f_denim, "vars": [
            {"vals": [c_azul, t_p, g_fem], "custo": 60, "venda": 139.9, "min": 7, "ideal": 15},
        ]},
        {"nome": "Jaqueta Corta-Vento", "cat": cat_casacos, "forn": f_casual, "vars": [
            {"vals": [c_preto, t_g, g_uni], "custo": 120, "venda": 279.9, "min": 3, "ideal": 9},
        ]},
        {"nome": "Meia Esportiva (Par)", "cat": cat_acessorios, "forn": f_malhas, "vars": [
            {"vals": [c_branco, t_unico, g_uni], "custo": 10, "venda": 29.9, "min": 20, "ideal": 100},
        ]},
    ]
    
    all_variations = []
    for p_data in produtos_data:
        produto, _ = Produto.objects.get_or_create(nome=p_data["nome"], categoria=p_data["cat"], fornecedor=p_data["forn"])
        for v_data in p_data["vars"]:
            variacao, _ = Variacao.objects.get_or_create(
                produto=produto, 
                preco_de_custo=v_data["custo"], 
                preco_de_venda=v_data["venda"], 
                estoque_minimo=v_data["min"], 
                estoque_ideal=v_data["ideal"]
            )
            variacao.valores_atributos.set(v_data["vals"])
            all_variations.append(variacao)

    # --- PASSO 5: Simular Histórico de Movimentações ---
    
    # Estoques iniciais (90 dias atrás)
    start_date = date(2025, 8, 1)
    for v in all_variations:
        initial_stock = v.estoque_ideal * random.randint(2, 4) # Começa com bastante stock
        MovimentacaoEstoque.objects.create(variacao=v, quantidade=initial_stock, tipo='ENTRADA', data=timezone.make_aware(datetime.combine(start_date, time(9,0))))

    # Simulação de vendas diárias
    current_date = start_date
    end_date = date(2025, 10, 8)
    
    while current_date <= end_date:
        # Simula entre 1 e 12 vendas por dia
        num_sales = random.randint(1, 12)
        for _ in range(num_sales):
            # Escolhe um produto aleatório para vender
            v_to_sell = random.choice(all_variations)
            # Simula a quantidade vendida
            quantity_sold = random.randint(1, 3)
            # Simula uma hora aleatória para a venda (horário comercial)
            sale_time = time(random.randint(9, 21), random.randint(0, 59))
            sale_datetime = timezone.make_aware(datetime.combine(current_date, sale_time))
            
            MovimentacaoEstoque.objects.create(
                variacao=v_to_sell, 
                quantidade=quantity_sold, 
                tipo='SAIDA', 
                data=sale_datetime
            )
        
        # Simula uma reposição de stock a cada 15 dias
        if current_date.day == 1 or current_date.day == 15:
            v_to_restock = random.choice(all_variations)
            restock_quantity = v_to_restock.estoque_ideal * 2
            restock_datetime = timezone.make_aware(datetime.combine(current_date, time(10,0)))
            MovimentacaoEstoque.objects.create(
                variacao=v_to_restock,
                quantidade=restock_quantity,
                tipo='ENTRADA',
                data=restock_datetime,
                descricao="Reposição quinzenal"
            )
            
        current_date += timedelta(days=1)


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0003_fornecedor_tempo_entrega_dias_and_more'), # Verifique se este é o nome da sua migração anterior
    ]

    operations = [
        migrations.RunPython(popular_dados_iniciais),
    ]

