🚀 Gestor de Estoque Inteligente v2.5
Um sistema completo para gestão de estoque e ponto de venda (PDV), desenvolvido em Django com uma interface moderna e intuitiva inspirada nos princípios de design da Apple.

Este projeto foi criado como uma solução robusta para pequenas e médias empresas do setor de vestuário, permitindo um controle detalhado de produtos com variações, gestão de compras preditiva e uma frente de caixa rápida para o dia a dia.

🔗 Prévia Navegável (Live Demo): fernando05490.pythonanywhere.com

✨ Funcionalidades Principais
Dashboard de BI: Visão geral completa da saúde do negócio com cards de resumo e gráficos interativos.

Controle de Variações: Gestão de produtos complexos com múltiplos atributos (Tamanho, Cor, Estilo, etc.).

Módulo de Compras Preditivo: Lista de reposição inteligente que sugere o que comprar com base na média de vendas e no tempo de entrega do fornecedor.

Frente de Caixa (PDV): Interface de ponto de venda rápida com busca de produtos em tempo real e baixa automática de estoque.

Relatórios Interativos: Análise de desempenho com gráficos de drill-down clicáveis.

Exportação para PDF: Geração de relatórios financeiros profissionais e personalizáveis.

Sistema de Permissões: Controle de acesso com diferentes níveis de usuário (Gerentes vs. Vendedores).

Design Premium: Interface inspirada na Apple, com tema claro/escuro e foco na experiência do usuário.

💻 Tecnologias Utilizadas
Back-End: Python, Django

Front-End: HTML5, CSS3, JavaScript, Bootstrap 5

Banco de Dados: SQLite

Bibliotecas Principais: WeasyPrint (PDFs), Chart.js (Gráficos), Flatpickr (Calendários)

🚀 Como Executar Localmente
Siga este guia detalhado para configurar e rodar o projeto na sua máquina.

1. Pré-requisitos
Antes de começar, garanta que você tenha os seguintes programas instalados:

Python (versão 3.10 ou superior): Baixe aqui

Importante: Durante a instalação no Windows, marque a caixa "Add Python to PATH".

Git: Baixe aqui

(Apenas para Windows) GTK for WeasyPrint: A biblioteca de PDF (WeasyPrint) precisa de uma dependência externa no Windows. Se este passo for pulado, a instalação no Passo 4 falhará.

Siga o guia oficial de instalação do GTK via MSYS2: Instruções aqui.

Após instalar, o passo mais importante é adicionar a pasta do GTK ao Path do Windows (geralmente C:\msys64\mingw64\bin).

2. Clonar o Repositório
Abra seu terminal (PowerShell, CMD, etc.) numa pasta de sua escolha e clone o projeto:

git clone [https://github.com/fernandinho05490/projeto-gestor-estoque.git](https://github.com/fernandinho05490/projeto-gestor-estoque.git)
cd projeto-gestor-estoque

3. Configurar o Ambiente Virtual
É crucial isolar as dependências do projeto.

Crie o ambiente virtual:

python -m venv venv

Ative o ambiente:

No Windows (PowerShell): .\venv\Scripts\Activate.ps1

No Mac/Linux: source venv/bin/activate

Seu terminal deve agora mostrar (venv) no início da linha.

4. Instalar as Dependências
Com o ambiente ativo, instale todas as bibliotecas Python necessárias com um único comando:

pip install -r requirements.txt

Se este passo falhar com um erro OSError sobre libgobject..., significa que o pré-requisito do GTK não foi instalado ou o terminal precisa ser reiniciado.

5. Configurar a Chave Secreta (.env)
A chave secreta não está no GitHub por segurança. Precisamos criá-la localmente.

Navegue até a pasta que contém o manage.py. A estrutura pode variar, mas o caminho geralmente é Suestoque/gestor_estoque/.

Dentro desta pasta, crie um novo arquivo chamado .env.

Para gerar uma nova chave, use o shell do Django. No terminal (na pasta do manage.py), rode:

python manage.py shell

Dentro do shell (>>>), cole os seguintes comandos:

from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
exit()

Copie a chave que foi impressa no terminal.

Abra o arquivo .env e cole a chave no seguinte formato:

SECRET_KEY='sua-chave-secreta-copiada-aqui'

6. Preparar o Banco de Dados
Aplique as migrações para criar as tabelas do banco de dados:

python manage.py migrate

Crie sua conta de administrador:

python manage.py createsuperuser

Siga as instruções para criar seu usuário e senha.

7. Iniciar o Servidor
Tudo pronto! Inicie o servidor de desenvolvimento:

python manage.py runserver

Acesse o sistema em https://www.google.com/search?q=http://127.0.0.1:8000/ e faça o login com o superusuário que você acabou de criar.

🔑 Contas de Acesso para Teste
Para explorar as diferentes funcionalidades e permissões, você pode usar as seguintes contas na prévia navegável:

Conta de Gerente (Acesso Total):

Usuário: admin

Senha: admin1234

Conta de Vendedor (Acesso Limitado):

Usuário: vendedor_teste

Senha: teste1234