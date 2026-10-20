"""Regras puras de seleção para autocomplete, independentes da interface gráfica."""
from __future__ import annotations

import unicodedata
from typing import Optional
from collections.abc import Iterable


def normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(ch for ch in texto if not unicodedata.combining(ch)).casefold().strip()


def nome_base_sugestao(valor: str) -> str:
    """Remove a descrição visual da sugestão, preservando o nome do produto."""
    return str(valor or "").split(" — ", 1)[0].strip()


def selecionar_sugestao(termo: str, sugestoes: Iterable[str], destacada: str | None = None) -> str | None:
    """Prioriza seleção por setas, depois correspondência exata e por fim a primeira opção."""
    itens = list(sugestoes or [])
    if not itens:
        return None
    if destacada in itens:
        return destacada
    normalizado = normalizar_texto(nome_base_sugestao(termo))
    if normalizado:
        for item in itens:
            if normalizar_texto(nome_base_sugestao(item)) == normalizado:
                return item
    return itens[0]
