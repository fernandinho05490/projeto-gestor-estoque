#!/bin/bash
echo "=== Iniciando Celery Worker ==="
echo "Diretório atual: $(pwd)"
echo "Conteúdo do diretório:"
ls -la

echo "=== Configurando PythonPath ==="
export PYTHONPATH=/app/gestor_estoque:$PYTHONPATH
echo "PYTHONPATH: $PYTHONPATH"

echo "=== Testando imports ==="
cd /app/gestor_estoque
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestor_estoque.settings')
import django
django.setup()
print('Django configurado!')
from gestor_estoque.celery import app
print('Celery importado!')
"

echo "=== Iniciando Celery ==="
celery -A gestor_estoque.celery worker --loglevel=info