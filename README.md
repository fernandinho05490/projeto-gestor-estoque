# 🚀 Gestor de Estoque Inteligente

Este projeto é um sistema de gestão de estoque e análise de vendas desenvolvido com Django.

---

## ✨ Prévia Navegável (Live Demo)

Você pode testar o sistema completo, em tempo real, no seguinte link:

**[https://fernando05490.pythonanywhere.com/](https://fernando05490.pythonanywhere.com/)**

---

## 🔑 Contas de Acesso para Teste

Para explorar as diferentes funcionalidades e permissões, você pode usar as seguintes contas:

* **Conta de Gerente (Acesso Total):**
    * **Usuário:** `[admin]`
    * **Senha:** `[admin1234]`

* **Conta de Vendedor (Acesso Limitado):**
    * **Usuário:** `vendedor_teste`
    * **Senha:** `[teste1234]`

---

## 📸 Screenshots

Aqui estão algumas telas do sistema em funcionamento:

**Dashboard Principal**
*[Insira aqui um print da tela principal]*

**Relatório de Vendas Detalhado**
*[Insira aqui um print da tela de relatório]*

---

## 🛠️ Como Executar Localmente

Se desejar rodar o projeto na sua própria máquina, siga os passos:

1.  Clone o repositório: `git clone https://github.com/fernandinho05490/projeto-gestor-estoque`
2.  Crie e ative um ambiente virtual: `python -m venv venv` e `.\venv\Scripts\Activate.ps1`
3.  Instale as dependências: `pip install -r requirements.txt`
4.  Crie um arquivo `.env` na pasta `gestor_estoque/` com sua `SECRET_KEY`.
5.  Rode as migrações: `python manage.py migrate`
6.  Inicie o servidor: `python manage.py runserver`
