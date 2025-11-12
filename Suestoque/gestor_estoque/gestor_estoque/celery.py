import os
from celery import Celery

# Define o módulo de settings padrão do Django para o 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_estoque.settings')

app = Celery('gestor_estoque') # Use o nome do seu projeto

# Usa string aqui para que o worker não precise serializar
# o objeto de configuração diretamente.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega módulos 'tasks.py' de todos os apps registrados no Django
app.autodiscover_tasks()