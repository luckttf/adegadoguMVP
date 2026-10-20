# Checklist de release e validação operacional

A versão só deve ser promovida de candidata a release estável depois que os itens abaixo forem verificados no Windows de destino.

## Código e automação

- [ ] `python -m compileall -q .` finaliza sem erro.
- [ ] `python -m unittest discover -s tests -v` aprova toda a suíte.
- [ ] A versão, o changelog e o README correspondem ao pacote entregue.
- [ ] O Git não inclui banco, backups, logs, `.venv`, tokens ou dados de cliente.

## Banco e migração

- [ ] Backup manual da base que será atualizada.
- [ ] Validação da migração em uma cópia da base de origem.
- [ ] Conferência de contagem de produtos, vendas, itens, pagamentos, dias, histórico e garrafas abertas.
- [ ] Comparação de totais financeiros agregados antes/depois, investigando toda divergência.
- [ ] Restauração ensaiada com o programa fechado e integridade SQLite confirmada.
- [ ] Diretório de backup fora do repositório e cópia adicional separada do computador.

## PDV e estoque

- [ ] Pesquisa por nome e código de barras; Enter, teclado numérico Enter, setas, Tab e Shift+Tab.
- [ ] Estoque insuficiente, quantidade inválida e desconto fora da faixa são recusados.
- [ ] Venda em pagamento único e venda em pagamento dividido conciliam com o total.
- [ ] Fiado exige cliente, baixa estoque no momento da entrega e não aparece como dinheiro recebido.
- [ ] Recebimento do fiado exige que os valores somem ao total devido e entra no dia do recebimento.
- [ ] Doses consomem garrafas abertas pela ordem correta; abertura nova exige confirmação.
- [ ] Perda, ajuste e encerramento de garrafa ficam rastreados e garrafa fechada não pode ser reativada.
- [ ] Falha deliberada em etapa transacional não deixa venda/estoque em estado parcial.

## Interface e histórico

- [ ] Todas as abas testadas em tema claro e escuro, alternando várias vezes.
- [ ] Listas não mantêm fundos ou texto da paleta anterior.
- [ ] Histórico navega até o último registro e o filtro de data reinicia a página.
- [ ] Dias navega além da primeira página e apresenta todos os registros antigos.
- [ ] Pedidos/fiado navega além da primeira página; o recebimento de um fiado carrega apenas a venda selecionada.
- [ ] Estados vazios, mensagens de erro e janelas de detalhe têm contraste adequado.
- [ ] Redimensionamento e resolução mínima não ocultam controles importantes.

## Operação diária

- [ ] Abertura e fechamento de dia conferidos.
- [ ] Valores vendidos, valores efetivamente recebidos, descontos, lucro estimado e fiado em aberto conciliados.
- [ ] O arquivo `barns.log` não contém exceções inexplicadas.
- [ ] Operadores sabem realizar backup e quem pode restaurá-lo.
- [ ] A instalação oficial aponta para o caminho esperado do banco, sem dados de demonstração.

## Pós-release

- [ ] Registrar versão/tag no Git.
- [ ] Guardar o pacote instalado e seu hash junto à release.
- [ ] Manter a última versão conhecida como boa e o backup anterior até concluir período combinado de validação.
