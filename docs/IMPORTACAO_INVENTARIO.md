# Preparação do inventário oficial por CSV

A base utilizada durante o desenvolvimento é demonstrativa. A implantação real deve começar por uma contagem física e um arquivo revisado — não pela promoção automática dos produtos de teste.

## Fluxo recomendado

1. Contar fisicamente cada produto e identificar nome, marca/variante, categoria, unidade e código de barras quando disponível.
2. Registrar quantidade real em unidades fechadas; contar separadamente garrafas já abertas e medir o saldo físico de doses quando isso fizer parte do controle de abertura.
3. Conferir com quem compra os preços de custo reais, preço de venda atual, preço por dose e rendimento por garrafa.
4. Gerar o CSV em UTF-8, com cabeçalho e uma linha por produto.
5. Revisar duplicatas de nomes/códigos de barras, números não positivos, vírgula decimal, produtos sem categoria e preços ausentes.
6. Executar uma pré-validação e produzir relatório de linhas aceitas/rejeitadas antes de escrever no banco.
7. Fazer backup da base vazia/configuração de destino; importar dentro de transação; reler produtos e comparar totais da planilha com os gravados.
8. Só ativar o catálogo após aprovação manual da pré-visualização e da reconciliação.

## Colunas propostas

| Coluna | Obrigatória | Significado |
|---|---|---|
| `nome` | Sim | Nome comercial único do produto |
| `categoria` | Recomendada | Categoria já existente ou a criar após revisão |
| `codigo_barras` | Não | Código como texto, preservando zeros à esquerda |
| `quantidade` | Sim | Quantidade de unidades fechadas, inteiro não negativo |
| `preco_custo` | Sim para inventário oficial | Custo atual por unidade de estoque |
| `preco` | Sim | Preço de venda por unidade |
| `estoque_minimo` | Recomendada | Limite inferior de alerta |
| `estoque_medio` | Recomendada | Limite de estoque médio |
| `is_garrafa` | Sim | `sim` ou `nao`, conforme política acordada |
| `volume_garrafa_ml` | Para garrafas | Volume nominal da garrafa em ml |
| `doses_por_garrafa` | Para garrafas vendidas por dose | Rendimento operacional estimado e confirmado |
| `preco_dose` | Para garrafas vendidas por dose | Preço unitário da dose vendida |

O contrato final será ajustado ao processo de contagem real antes de implementar o importador. Não misture estoque de unidades fechadas com dose remanescente de garrafa aberta em uma única coluna. Valores monetários devem ser interpretados de modo explícito (por exemplo, `12,50` ou `12.50` conforme o importador definido), nunca por tentativa silenciosa.

## Critérios de aceitação

- Mostrar prévia da quantidade de linhas e valores normalizados.
- Informar número da linha e motivo para cada erro, sem descartar falhas em silêncio.
- Não duplicar o produto ao executar a mesma importação duas vezes sem uma decisão explícita de atualização.
- Não substituir preço, custo ou estoque existentes sem uma política explícita de conflito.
- Permitir cancelar antes de gravar e reverter todas as gravações em caso de falha.
- Gerar resumo de quantos produtos foram inseridos/atualizados/rejeitados.
- Preservar código de barras como texto e validar duplicatas antes do commit.
