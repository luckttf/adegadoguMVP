# Colocar o BARNS Adega no Git

Este pacote está preparado para Git, mas não contém um remoto GitHub porque a URL do repositório ainda não foi definida.

## 1. Revise o que vai ser versionado

Abra PowerShell na pasta raiz do projeto e confira:

```powershell
git status --short
```

A pasta não deve conter `adega_dados.db`, arquivos SQLite, `backups/`, `barns.log`, `.venv/`, `.env` ou credenciais. O `.gitignore` cobre esses itens, mas sempre revise `git status` antes de cada commit.

## 2. Inicialize e faça o primeiro commit

```powershell
git init
git add -A
git status --short
git diff --cached --stat
git commit -m "chore: prepare BARNS Adega release candidate"
git branch -M main
```

Se o Git ainda não conhece sua identidade, configure `user.name` e `user.email` conscientemente antes de repetir o commit. Não use um endereço de e-mail privado se não quiser expô-lo no histórico.

## 3. Conecte um remoto

Crie um repositório vazio no provedor escolhido e substitua usuário/nome pela URL real. Então execute:

```powershell
git remote add origin "https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git"
git push -u origin main
```

Não crie um repositório público antes de decidir licença e confirmar que nenhum dado privado foi adicionado.

## 4. Fluxo de trabalho sugerido

```powershell
git switch -c fix/paginacao-historico
# editar e testar
python -m compileall -q .
python -m unittest discover -s tests -v
git diff
git add <arquivos-alterados>
git commit -m "fix: paginar histórico sem truncar registros"
git switch main
git merge --no-ff fix/paginacao-historico
```

Para uma equipe ou para produção, prefira pull requests/revisão ao merge direto e mantenha um tag por release validada.
