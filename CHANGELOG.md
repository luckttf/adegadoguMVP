# Changelog

Changes that matter to users and maintainers are recorded here.

## 0.1.0-rc.1 — Estabilização de histórico e preparação de release

- Histórico de movimentações passa a mostrar linhas compactas e navegar em páginas de 30 itens.
- Dias de operação passam a navegar em páginas de 25 itens; o total é contado separadamente da página atual.
- Pedidos/fiado passam a paginar 25 vendas, e a busca de uma venda para quitação consulta somente o registro solicitado.
- Consultas de histórico ganham identificador/origem e ordenação determinística para impedir repetição ou omissão entre páginas em caso de datas iguais.
- A alternância de tema sincroniza a superfície interna de listas roláveis e atualiza conteúdo de listas com a nova paleta, sem recriar os campos do PDV.
- Cores semânticas distintas para texto sobre marca e texto sobre ação de alerta evitam colisões no mapeamento claro/escuro.
- Adicionados testes que cobrem múltiplas páginas de dias, histórico e vendas, confirmando ausência de registros ausentes ou duplicados.
- Totais de fiado são calculados por consulta agregada; relatórios/fechamento deixam de carregar todas as vendas e seus itens apenas para somar o saldo pendente.
- README, documentação de arquitetura, segurança, guia de Git, importação futura do inventário, guia diário e checklist de release adicionados.
- Adicionada verificação automatizada de compilação/testes no GitHub Actions para Windows e Ubuntu.

## 0.1.0-rc.0 — Redesign administrativo

- Primeira padronização das páginas administrativas, navegação e cabeçalho compartilhado.
- Tema claro e modo noturno, preferência persistida e navegação por teclado.
- Núcleo de vendas, fiado, estoque, garrafas e backup separado em serviços/repositórios.
