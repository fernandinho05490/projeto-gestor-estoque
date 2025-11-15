# main.py - Corrigido
import os
import sys

# Adicionar o caminho do Django ao Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Suestoque', 'gestor_estoque'))

try:
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_estoque.settings')
    
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    
    print("✅ Django carregado com sucesso!")
    
except Exception as error:  # ← CORRIGIDO: 'error' em vez de 'e'
    # Fallback se Django falhar
    print(f"❌ Erro ao carregar Django: {error}")
    
    def app(environ, start_response):
        data = f"Erro ao carregar Django: {error}\n".encode()  # ← CORRIGIDO: 'error'
        status = '500 Internal Server Error'
        response_headers = [
            ('Content-type', 'text/plain'),
            ('Content-Length', str(len(data)))
        ]
        start_response(status, response_headers)
        return iter([data])
    
    application = app