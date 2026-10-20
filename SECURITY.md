# Segurança e tratamento de dados

## Dados sensíveis

O banco local pode conter vendas, nomes de clientes, pagamentos e movimentações. Não anexe `adega_dados.db`, backups, logs ou exportações reais a issues públicas ou repositórios públicos.

## Relato de vulnerabilidade/erro com risco de dados

Não publique dados reais nem detalhes exploráveis em um repositório público. Documente os passos de reprodução usando uma base sintética e compartilhe o relatório em canal privado com o mantenedor.

## Backup e recuperação

- Faça uma cópia antes de atualizar o aplicativo ou alterar o esquema.
- Nunca copie ou substitua um banco em uso.
- Após criar uma cópia, valide a integridade SQLite e, periodicamente, realize uma restauração de teste.
- Um backup no mesmo disco não protege contra falha física, roubo ou ransomware; mantenha cópia adicional em local separado, protegido e com acesso restrito.

## Princípios de desenvolvimento

- Use SQL parametrizado.
- Valide entradas na camada de negócio e restrinja estados inválidos na persistência.
- Prefira migrações aditivas e testadas.
- Não registre senhas, tokens ou dados desnecessários no log.
- Antes de permitir dois terminais simultâneos, migre para arquitetura de banco centralizado com concorrência e autenticação projetadas para isso.
