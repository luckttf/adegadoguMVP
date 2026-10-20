# Arquitetura e limites

## Direção das dependências

- `ui/` cuida de layout, input, feedback e navegação; não deve decidir regras de estoque ou lucro.
- `domain/` contém regras puras que podem ser testadas sem janela ou banco, quando viável.
- `services/` coordena fluxos de aplicação e integra operações transacionais.
- `infrastructure/database/` contém conexão, esquema/migrações e repositórios SQLite.
- `database.py` é uma fachada de compatibilidade temporária; novos módulos devem preferir dependências específicas e migração gradual das chamadas existentes.

## Invariantes essenciais

- Uma venda confirmada e as alterações de estoque/doses relacionadas devem ser atômicas.
- A persistência valida preços, quantidade, descontos, dia operacional e pagamentos mesmo quando o chamador é a interface.
- O histórico deve ser auditável e não deve ser removido para corrigir um lançamento; use estorno ou ajuste.
- O total pago precisa conciliar com o total devido; fiado é obrigação de recebimento, não dinheiro no caixa.
- Paginação é uma preocupação da consulta/tela, não uma política de retenção.
- Migrações são aditivas por padrão e devem ter teste de compatibilidade com estruturas antigas.

## Persistência e concorrência

SQLite local é adequado ao modo atual de um único computador. Não compartilhe o arquivo DB por rede para operar simultaneamente em duas máquinas. Para isso será necessário servidor de banco, caminho de acesso autenticado, tratamento de concorrência, sessão de usuário e teste de recuperação.

## Observabilidade

Falhas da aplicação devem ser registradas em `barns.log`, sem incluir segredos ou dados pessoais desnecessários. Erros operacionais devem ser apresentados com linguagem útil ao operador e manter o detalhe técnico no log.
