# startup.py - Script de inicialização para App Engine
import os
import django
import sys

# Configurar Django
sys.path.append(os.path.join(os.path.dirname(__file__), 'Suestoque', 'gestor_estoque'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_estoque.settings')
django.setup()

from django.core.management import execute_from_command_line

print("=== INICIANDO SETUP DO BANCO DE DADOS ===")

# Aplicar migrations
try:
    execute_from_command_line(['manage.py', 'migrate'])
    print("✅ Migrations aplicadas com sucesso!")
except Exception as e:
    print(f"❌ Erro nas migrations: {e}")

# Criar usuário admin
from django.contrib.auth import get_user_model
User = get_user_model()

try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("✅ Usuário admin criado: admin / admin123")
    else:
        print("✅ Usuário admin já existe")
except Exception as e:
    print(f"❌ Erro ao criar usuário: {e}")

print("=== SETUP CONCLUÍDO ===")
