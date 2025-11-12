import pyopencl as cl
import numpy as np

def test_opencl():
    try:
        print("🔍 Procurando plataformas OpenCL...")
        platforms = cl.get_platforms()
        print(f"✅ Encontradas {len(platforms)} plataforma(s)")
        
        for i, platform in enumerate(platforms):
            print(f"\n--- Plataforma {i} ---")
            print(f"Nome: {platform.name}")
            print(f"Vendor: {platform.vendor}")
            print(f"Versão: {platform.version}")
            
            devices = platform.get_devices()
            print(f"Dispositivos: {len(devices)}")
            for j, device in enumerate(devices):
                print(f"  Dispositivo {j}: {device.name}")
                print(f"    Tipo: {cl.device_type.to_string(device.type)}")
        
        # Teste simples
        if len(platforms) > 0:
            platform = platforms[0]
            context = cl.Context([platform.get_devices()[0]])
            print(f"\n🎉 OpenCL funcionando! Contexto criado com: {platform.get_devices()[0].name}")
            return True
        else:
            print("❌ Nenhuma plataforma OpenCL encontrada")
            return False
            
    except Exception as e:
        print(f"❌ Erro no OpenCL: {e}")
        return False

if __name__ == "__main__":
    test_opencl()