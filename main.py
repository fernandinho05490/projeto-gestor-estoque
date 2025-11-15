# main.py - Com inicialização
import os
import sys

# Executar script de startup
try:
    from startup import *
    print("✅ Startup executado com sucesso!")
except Exception as e:
    print(f"❌ Erro no startup: {e}")

# Adicionar o caminho do Django ao Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Suestoque', 'gestor_estoque'))

try:
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_estoque.settings')
    
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    
    print("✅ Django carregado com sucesso!")
    
except Exception as error:
    print(f"❌ Erro ao carregar Django: {error}")
    
    def app(environ, start_response):
        data = f"Erro ao carregar Django: {error}\n".encode()
        status = '500 Internal Server Error'
        response_headers = [
            ('Content-type', 'text/plain'),
            ('Content-Length', str(len(data)))
        ]
        start_response(status, response_headers)
        return iter([data])
    
    application = app