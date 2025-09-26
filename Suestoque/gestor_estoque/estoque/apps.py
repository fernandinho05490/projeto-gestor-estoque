# estoque/apps.py

from django.apps import AppConfig

class EstoqueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estoque'

    def ready(self):
        import estoque.signals  # Importa os sinais para que eles sejam registrados