# 🏋️‍♀️ Centro de Treinamento RV

Sistema completo para gerenciamento de alunos e controle de mensalidades de academia.

## 🚀 Funcionalidades

- 👤 Cadastro de alunos
- 🌐 Cadastro público via link
- 💰 Controle de mensalidades
- ⏰ Verificação automática de vencimentos
- 📊 Dashboard administrativo
- 🗂️ Inicialização automática do banco de dados

## 🧠 Como o sistema funciona

Ao iniciar o sistema:

- Cria as tabelas do banco de dados automaticamente
- Executa migrações, se necessário
- Insere dados iniciais
- Verifica vencimentos de mensalidades
- Disponibiliza:
  - Dashboard administrativo
  - Página de cadastro público

## 🌐 Acesso ao sistema

Após iniciar:

- Sistema: http://localhost:8060  
- Cadastro público: http://localhost:8060/cadastro  

## 🛠️ Tecnologias utilizadas

- Python
- Flask / Dash
- Waitress (servidor)
- SQLite (ou outro banco, se aplicável)

## ⚙️ Como executar o projeto

1. Crie um ambiente virtual:
