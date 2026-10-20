# Contribuindo para o BARNS Adega

O projeto prioriza correção financeira, integridade do estoque, rastreabilidade e operação rápida. Mudanças visuais não devem alterar regras de negócio incidentalmente.

## Antes de alterar código

1. Atualize a branch e crie uma branch para a mudança.
2. Nunca use a base operacional para testes; cada teste deve apontar para um banco temporário.
3. Identifique a regra de negócio envolvida e adicione teste de regressão antes de corrigir um bug.
4. Para alterações no esquema, escreva migração aditiva e teste-a contra uma estrutura legada representativa.

## Verificações obrigatórias

```powershell
python -m compileall -q .
python -m unittest discover -s tests -v
```

Para alterações de interface, valide manualmente tema claro/escuro, Tab/Shift+Tab, Enter/Space, estados vazios, mensagens de erro, redimensionamento e preservação do carrinho/estado de filtros.

## Convenções

- Nomes, mensagens e documentação em português brasileiro, mantendo termos técnicos consagrados quando útil.
- Mantenha SQL parametrizado; não concatene dados fornecidos pelo usuário em consultas.
- Dinheiro deve usar as funções monetárias e regras de arredondamento existentes. Não introduza cálculos monetários dispersos na UI.
- Operações que afetam venda, estoque, doses e recebimentos devem ser transacionais e idempotentes quando aplicável.
- Não apague histórico para corrigir estado; prefira estorno, ajuste auditável ou migração documentada.
- Preserve APIs públicas reexportadas por `database.py` até que a camada de compatibilidade seja removida em migração separada.
- Não introduza dependências novas sem justificar seu uso e registrar a versão mínima necessária.

## Commits

Use mensagens que identifiquem a intenção, por exemplo `fix: paginar histórico sem truncar registros`, `test: cobrir navegação entre páginas` e `docs: documentar recuperação de backup`.
