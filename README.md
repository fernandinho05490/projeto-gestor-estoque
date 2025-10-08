🚀 Gestor de Estoque Inteligente v2.5
Este projeto é um sistema de gestão de estoque e análise de vendas desenvolvido com Django, com uma interface moderna e foco na experiência do usuário.

🔗 Prévia Navegável (Live Demo)
Você pode testar o sistema completo, em tempo real, no seguinte link:

https://fernando05490.pythonanywhere.com/

🔑 Contas de Acesso para Teste
Para explorar as diferentes funcionalidades e permissões, você pode usar as seguintes contas na prévia online:

Conta de Gerente (Acesso Total):

Usuário: admin

Senha: admin1234

Conta de Vendedor (Acesso Limitado):

Usuário: vendedor_teste

Senha: teste1234

📸 Screenshots
Aqui estão algumas telas do sistema em funcionamento:

(Insira aqui um print da tela principal)

(Insira aqui um print da tela de relatório)

⚙️ Como Executar Localmente
Se desejar rodar o projeto na sua própria máquina, siga os passos:

Pré-requisitos
Antes de continuar, garanta que você tem o Git e o Python instalados. Se você estiver no Windows e quiser usar a funcionalidade de exportar PDF, instale também o GTK.

Python (3.10+): Baixe aqui https://www.python.org/downloads/

Git: Baixe aqui https://git-scm.com/downloads

GTK (para WeasyPrint no Windows): Instruções aqui https://www.google.com/search?q=https://doc.courtbouillon.org/weasyprint/stable/first_steps.html%23windows (Siga os passos de instalação do MSYS2 e adicione C:\msys64\mingw64\bin ao Path do sistema).

Passos de Instalação
1. Clone o repositório:

git clone [https://github.com/fernandinho05490/projeto-gestor-estoque.git](https://github.com/fernandinho05490/projeto-gestor-estoque.git)
cd projeto-gestor-estoque

2. Crie e ative um ambiente virtual:

python -m venv venv
.\venv\Scripts\Activate.ps1

3. Instale as dependências:

pip install -r requirements.txt

4. Crie um arquivo .env na pasta Suestoque/gestor_estoque/ com sua SECRET_KEY.

Para gerar uma chave, use o shell do Django:

python manage.py shell

Dentro do shell (>>>), cole:

from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
exit()

Copie a chave gerada e cole no seu arquivo .env no formato: SECRET_KEY='sua-chave-aqui'

5. Rode as migrações do banco de dados:

python manage.py migrate

6. Crie um superusuário (administrador):

python manage.py createsuperuser

7. Inicie o servidor:

python manage.py runserver
