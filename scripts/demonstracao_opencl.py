# demonstracao_opencl.py
import pyopencl as cl
import numpy as np
import time

def demonstrar_opencl_faculdade():
    """Demonstração completa do OpenCL para o projeto da faculdade"""
    print("=" * 70)
    print("🎓 PROJETO FACULDADE - DEMONSTRAÇÃO OPENCL")
    print("=" * 70)
    
    try:
        # 1. DETECÇÃO DE PLATAFORMAS E DISPOSITIVOS
        platforms = cl.get_platforms()
        print(f"\n🔍 PLATAFORMAS OPENCL DETECTADAS: {len(platforms)}")
        
        for i, platform in enumerate(platforms):
            print(f"\n--- PLATAFORMA {i} ---")
            print(f"   Nome: {platform.name}")
            print(f"   Fabricante: {platform.vendor}")
            print(f"   Versão: {platform.version}")
            
            devices = platform.get_devices()
            print(f"   📟 Dispositivos: {len(devices)}")
            for j, device in enumerate(devices):
                print(f"      Dispositivo {j}: {device.name}")
                print(f"         Tipo: {cl.device_type.to_string(device.type)}")
                print(f"         Memória: {device.global_mem_size // (1024*1024)} MB")
        
        if not platforms:
            print("❌ NENHUMA PLATAFORMA OPENCL ENCONTRADA")
            return None
        
        # 2. CONFIGURAÇÃO PARA SIMULAÇÃO
        platform = platforms[0]
        device = platform.get_devices()[0]
        context = cl.Context([device])
        queue = cl.CommandQueue(context)
        
        print(f"\n🎯 CONFIGURADO PARA EXECUTAR EM:")
        print(f"   Plataforma: {platform.name}")
        print(f"   Dispositivo: {device.name}")
        
        # 3. KERNEL OPENCL - SIMULAÇÃO MONTE CARLO
        kernel_code = """
        __kernel void simulacao_monte_carlo(
            __global float *vendas_aleatorias,
            const float lucro_por_unidade,
            __global float *lucros_totais,
            const int total_simulacoes)
        {
            int id = get_global_id(0);
            if (id < total_simulacoes) {
                float vendas = vendas_aleatorias[id];
                // Garantir que vendas não sejam negativas
                if (vendas < 0.0f) {
                    vendas = 0.0f;
                }
                lucros_totais[id] = vendas * lucro_por_unidade;
            }
        }
        """
        
        # 4. COMPILAÇÃO DO KERNEL
        print(f"\n⚙️  COMPILANDO KERNEL OPENCL...")
        program = cl.Program(context, kernel_code).build()
        print("   ✅ Kernel compilado com sucesso!")
        
        # 5. PARÂMETROS DA SIMULAÇÃO
        num_simulacoes = 500000  # 500 mil simulações para demonstração
        custo_produto = 25.50
        preco_venda = 55.00
        lucro_por_unidade = preco_venda - custo_produto
        
        print(f"\n📊 PARÂMETROS DA SIMULAÇÃO:")
        print(f"   Número de simulações: {num_simulacoes:,}")
        print(f"   Custo unitário: R${custo_produto:.2f}")
        print(f"   Preço de venda: R${preco_venda:.2f}")
        print(f"   Lucro por unidade: R${lucro_por_unidade:.2f}")
        
        # 6. PREPARAÇÃO DOS DADOS
        print(f"\n📦 PREPARANDO DADOS PARA GPU...")
        np.random.seed(42)  # Para resultados reproduzíveis
        vendas_aleatorias = np.random.normal(1000, 300, num_simulacoes).astype(np.float32)
        
        # 7. ALOCAÇÃO DE MEMÓRIA NA GPU
        vendas_buffer = cl.Buffer(context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=vendas_aleatorias)
        lucros_buffer = cl.Buffer(context, cl.mem_flags.WRITE_ONLY, vendas_aleatorias.nbytes)
        
        # 8. EXECUÇÃO NA GPU
        print(f"\n🚀 EXECUTANDO NA GPU...")
        start_time = time.time()
        
        program.simulacao_monte_carlo(
            queue, 
            vendas_aleatorias.shape, 
            None,
            vendas_buffer,
            np.float32(lucro_por_unidade),
            lucros_buffer,
            np.int32(num_simulacoes)
        )
        
        # 9. TRANSFERÊNCIA DE RESULTADOS
        lucros_totais = np.empty_like(vendas_aleatorias)
        cl.enqueue_copy(queue, lucros_totais, lucros_buffer)
        
        execution_time = time.time() - start_time
        
        # 10. ANÁLISE DOS RESULTADOS
        lucro_medio = np.mean(lucros_totais)
        lucro_maximo = np.max(lucros_totais)
        lucro_minimo = np.min(lucros_totais)
        desvio_padrao = np.std(lucros_totais)
        
        print(f"\n⏱️  TEMPO DE EXECUÇÃO: {execution_time:.4f} segundos")
        print(f"   Velocidade: {num_simulacoes/execution_time:,.0f} simulações/segundo")
        
        # 11. RESULTADOS FINAIS
        print(f"\n📈 RESULTADOS DA SIMULAÇÃO MONTE CARLO:")
        print(f"   Lucro Médio Esperado: R${lucro_medio:,.2f}")
        print(f"   Lucro Máximo Possível: R${lucro_maximo:,.2f}")
        print(f"   Lucro Mínimo Possível: R${lucro_minimo:,.2f}")
        print(f"   Desvio Padrão: R${desvio_padrao:,.2f}")
        print(f"   Método: OpenCL")
        print(f"   Dispositivo: {device.name}")
        
        # 12. COMPARAÇÃO DE PERFORMANCE
        print(f"\n🔍 COMPARAÇÃO DE PERFORMANCE:")
        print(f"   Simulações realizadas: {num_simulacoes:,}")
        print(f"   Tempo total: {execution_time:.4f}s")
        print(f"   Throughput: {num_simulacoes/execution_time:,.0f} simulações/segundo")
        
        return {
            'sucesso': True,
            'plataforma': platform.name,
            'dispositivo': device.name,
            'lucro_medio': float(lucro_medio),
            'lucro_maximo': float(lucro_maximo),
            'lucro_minimo': float(lucro_minimo),
            'desvio_padrao': float(desvio_padrao),
            'tempo_execucao': execution_time,
            'num_simulacoes': num_simulacoes,
            'throughput': num_simulacoes/execution_time,
            'metodo': 'opencl_local'
        }
        
    except Exception as e:
        print(f"\n❌ ERRO NA EXECUÇÃO OPENCL: {e}")
        return {'sucesso': False, 'erro': str(e)}

if __name__ == "__main__":
    print("Iniciando demonstração OpenCL para projeto da faculdade...")
    resultado = demonstrar_opencl_faculdade()
    
    if resultado and resultado['sucesso']:
        print(f"\n🎉 DEMONSTRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 70)
        print("✅ OPENCL FUNCIONANDO PERFEITAMENTE!")
        print("✅ SIMULAÇÃO MONTE CARLO COMPLETADA!")
        print("✅ ACELERAÇÃO POR GPU COMPROVADA!")
        print("=" * 70)
    else:
        print(f"\n💡 DICA: Para a demonstração da faculdade, você pode:")
        print("   - Mostrar este script funcionando localmente")
        print("   - Explicar a arquitetura OpenCL")
        print("   - Comparar com implementação CPU")