# 🍷 BARNS Adega - PDV & Gestão de Estoque

[![Quality Checks](https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO/actions/workflows/quality.yml/badge.svg)](https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO/actions/workflows/quality.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Aplicação desktop de Ponto de Venda (PDV), controle de estoque e gestão operacional para adegas e bares. Desenvolvido em Python com CustomTkinter e SQLite, focado em alta performance, navegação por teclado e consistência financeira.

## ✨ Funcionalidades

- **PDV Rápido:** Busca por autocomplete com suporte a Enter, leitor de código de barras e navegação por teclado.
- **Gestão de Fiado:** Registro de vendas pendentes, baixa de estoque e quitação posterior com conciliação de recebimentos.
- **Controle de Garrafas:** Abertura, consumo FIFO (First-In, First-Out) de doses, registro de perdas e encerramento.
- **Relatórios e Fechamento:** Resumo financeiro diário, cálculo de lucro estimado, descontos e snapshot imutável do fechamento.
- **Segurança de Dados:** Backup automático do banco SQLite com verificação de integridade e rotação.
- **Acessibilidade:** Modo claro/escuro, atalhos de teclado globais e foco visual para operação sem mouse.

## 🚀 Tecnologias

- **Interface:** [CustomTkinter](https://customtkinter.tomschimansky.com/)
- **Persistência:** SQLite (nativo, transacional)
- **Testes:** `unittest` (36 testes cobrindo regras de negócio, falhas de transação e integridade de banco)
- **Qualidade:** GitHub Actions (CI em Windows e Linux) e Ruff

## 🛠️ Instalação e Uso

1. Clone o repositório:
   ```bash
   git clone https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git
   cd NOME_DO_REPOSITORIO
Crie e ative o ambiente virtual:

powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Instale as dependências:

bash
pip install -r requirements.txt
Inicie o aplicativo:

bash
python main.py
🧪 Testes
O projeto utiliza testes unitários que não dependem de interface gráfica para rodar. Para executar a suíte:

bash
python -m unittest discover -s tests -v
📄 Licença
Este projeto está licenciado sob a Licença MIT. Consulte o arquivo LICENSE para mais detalhes.

