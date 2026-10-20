# Guia de operação diária — BARNS Adega

Este guia descreve o fluxo recomendado para uma instalação local em um único computador. Os nomes exatos de botões podem mudar conforme futuras versões.

## Antes de abrir

1. Inicie o aplicativo no computador designado como terminal principal.
2. Confirme que o tema está legível e que o status do dia de operação corresponde ao estado esperado.
3. Inicie um novo dia de operação quando aplicável.
4. Verifique se o último backup foi criado e se há espaço livre no disco.

## Vendas

- Procure pelo nome ou leia o código de barras. Confira produto, quantidade e preço antes de finalizar.
- Use pagamento único sempre que possível. Em pagamento dividido, os valores informados precisam somar exatamente o total.
- Para fiado, selecione/identifique o cliente e confirme que o produto foi entregue. Não trate o fiado como dinheiro recebido.
- Se uma venda foi entregue, não tente “corrigir” o estoque apagando registros. Registre o recebimento, cancelamento ou ajuste pelo fluxo apropriado e preserve a trilha histórica.

## Garrafas e doses

- O sistema consome primeiro saldos de garrafas já abertas.
- Quando a venda exigir abrir uma garrafa fechada, confira o produto e confirme explicitamente.
- Registre perdas reais com motivo sempre que possível.
- Não reative uma garrafa encerrada; se houver divergência física, siga o procedimento de ajuste auditável.
- O rendimento é estimado: confira periodicamente o rendimento físico por marca/volume e atualize a ficha do produto se a política da adega mudar.

## Fechamento do dia

1. Confira o total vendido separado do total efetivamente recebido.
2. Revise os meios de pagamento e o saldo de fiado em aberto.
3. Verifique perdas e ajustes de estoque relevantes.
4. Confira o resumo e confirme o fechamento do dia.
5. Não altere manualmente os valores do banco para corrigir uma divergência. Documente o problema e use uma operação auditável.

## Se o aplicativo falhar

1. Anote o horário e a última ação realizada.
2. Consulte `barns.log` e copie o traceback completo sem compartilhar informações pessoais desnecessárias.
3. Encerre completamente o aplicativo antes de copiar ou restaurar o banco.
4. Faça uma cópia do banco atual antes de tentar restauração.
5. Restaure uma cópia de backup validada e abra o aplicativo com uma única instância.
6. Confira vendas e movimentações recentes antes de retomar a operação.

## Restrições do modo atual

- A instalação suportada para operação é um computador por vez.
- Não execute duas instâncias que compartilham o mesmo arquivo de banco de dados.
- Não coloque SQLite em pasta de rede para adicionar um segundo terminal. Isso requer migração e testes de uma arquitetura com banco servidor.
- Os produtos do banco de desenvolvimento são dados de teste e não devem ser considerados inventário real.
