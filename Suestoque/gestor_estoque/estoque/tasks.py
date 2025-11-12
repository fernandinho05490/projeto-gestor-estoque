from celery import shared_task
import pyopencl as cl
import numpy as np
import os

# =============================================================================
# FUNÇÕES DE SIMULAÇÃO (colocar sempre ANTES das tasks)
# =============================================================================

def setup_opencl_definitivo():
    """Configuração do OpenCL com fallback"""
    print("🔧 CONFIGURANDO OPENCL...")
    
    try:
        platforms = cl.get_platforms()
        if platforms:
            print(f"✅ OpenCL detectado: {len(platforms)} plataforma(s)")
            for i, platform in enumerate(platforms):
                print(f"  Plataforma {i}: {platform.name}")
            return platforms[0]
        else:
            print("❌ Nenhuma plataforma OpenCL encontrada")
    except Exception as e:
        print(f"❌ OpenCL falhou: {e}")
    
    print("🚨 Usando NumPy como fallback...")
    return None

def executar_simulacao_opencl(dados, platform):
    """Implementação OpenCL"""
    custo, novo_preco, num_simulacoes = dados
    lucro_por_unidade = novo_preco - custo
    
    print(f"🎯 Executando OpenCL: {platform.name}")
    
    try:
        # Criar contexto
        devices = platform.get_devices()
        context = cl.Context(devices)
        queue = cl.CommandQueue(context)
        
        # Kernel OpenCL
        kernel_code = """
        __kernel void monte_carlo(
            __global float *vendas,
            const float lucro_unidade,
            __global float *lucros,
            const int num_simulacoes)
        {
            int gid = get_global_id(0);
            if (gid < num_simulacoes) {
                float v = vendas[gid];
                if (v < 0.0f) v = 0.0f;
                lucros[gid] = v * lucro_unidade;
            }
        }
        """
        
        # Compilar
        program = cl.Program(context, kernel_code).build()
        
        # Dados
        np.random.seed(42)
        vendas_aleatorias = np.random.normal(1000, 300, num_simulacoes).astype(np.float32)
        
        # Buffers
        vendas_buffer = cl.Buffer(context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=vendas_aleatorias)
        lucros_buffer = cl.Buffer(context, cl.mem_flags.WRITE_ONLY, vendas_aleatorias.nbytes)
        
        # Executar
        program.monte_carlo(queue, vendas_aleatorias.shape, None, vendas_buffer, np.float32(lucro_por_unidade), lucros_buffer, np.int32(num_simulacoes))
        
        # Resultados
        lucros_totais = np.empty_like(vendas_aleatorias)
        cl.enqueue_copy(queue, lucros_totais, lucros_buffer)
        
        # Estatísticas
        return {
            'lucro_medio': float(np.mean(lucros_totais)),
            'lucro_maximo': float(np.max(lucros_totais)),
            'lucro_minimo': float(np.min(lucros_totais)),
            'metodo': 'opencl',
            'plataforma': platform.name
        }
        
    except Exception as e:
        print(f"❌ Erro OpenCL: {e}")
        raise

def executar_simulacao_numpy(dados):
    """Implementação NumPy fallback"""
    custo, novo_preco, num_simulacoes = dados
    lucro_por_unidade = novo_preco - custo
    
    print("🔄 Executando com NumPy...")
    
    # Gerar dados
    np.random.seed(42)
    cenarios_vendas = np.random.normal(1000, 300, num_simulacoes)
    cenarios_vendas = np.maximum(cenarios_vendas, 0)
    
    # Calcular
    lucros_totais = cenarios_vendas * lucro_por_unidade
    
    return {
        'lucro_medio': float(np.mean(lucros_totais)),
        'lucro_maximo': float(np.max(lucros_totais)),
        'lucro_minimo': float(np.min(lucros_totais)),
        'metodo': 'numpy_fallback',
        'plataforma': 'CPU/NumPy'
    }

def executar_simulacao_robusta(dados):
    """Função principal com fallback automático"""
    platform = setup_opencl_definitivo()
    
    if platform is None:
        return executar_simulacao_numpy(dados)
    
    try:
        return executar_simulacao_opencl(dados, platform)
    except Exception as e:
        print(f"🔄 OpenCL falhou, usando NumPy: {e}")
        return executar_simulacao_numpy(dados)

def executar_simulacao_para_faculdade():
    """Para demonstração da faculdade - tenta OpenCL local primeiro"""
    try:
        from demonstracao_opencl import demonstrar_opencl_faculdade
        resultado = demonstrar_opencl_faculdade()
        if resultado and resultado['sucesso']:
            return resultado
    except Exception as e:
        print(f"⚠️  Demonstração OpenCL falhou: {e}")
        pass
    
    # Fallback para Docker
    print("🔄 Usando fallback Docker...")
    return executar_simulacao_robusta((25.50, 55.00, 1000000))

# =============================================================================
# TASKS CELERY (sempre DEPOIS das funções)
# =============================================================================

@shared_task(bind=True)
def executar_simulacao_lucro(self, custo=25.50, novo_preco=55.00, num_simulacoes=1000000):
    """Task Celery com parâmetros padrão"""
    try:
        print(f"[TASK] Iniciando simulação: {num_simulacoes} cenários")
        print(f"[TASK] Custo: R${custo:.2f}, Preço: R${novo_preco:.2f}")
        
        # Usar a função robusta
        dados = (custo, novo_preco, num_simulacoes)
        resultado = executar_simulacao_robusta(dados)
        
        print(f"[TASK] Concluído via {resultado['metodo']}")
        print(f"[TASK] Lucro Médio: R${resultado['lucro_medio']:,.2f}")
        
        return resultado
        
    except Exception as e:
        error_msg = f"❌ ERRO: {str(e)}"
        print(error_msg)
        return {'erro': error_msg}

@shared_task(bind=True)
def executar_simulacao_comparativa(self):
    """Task para testar ambos os modos: GPU local e Docker"""
    print("🔍 INICIANDO TESTE COMPARATIVO...")
    
    # Tentar GPU local primeiro
    try:
        resultado = executar_simulacao_para_faculdade()
        if resultado and resultado.get('sucesso'):
            print("🎯 RESULTADO: Executado na GPU local com OpenCL")
            return resultado
        else:
            print("⚠️  GPU local não retornou resultado válido")
    except Exception as e:
        print(f"⚠️  GPU local não disponível: {e}")
    
    # Fallback para Docker
    print("🔄 Alternando para execução no Docker...")
    resultado = executar_simulacao_robusta((25.50, 55.00, 1000000))
    print(f"📊 RESULTADO: Executado no Docker via {resultado['metodo']}")
    
    return resultado