"""Persistência local e independente da interface para preferências do BARNS."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

MODO_PADRAO = "claro"
MODOS_VALIDOS = {"claro", "escuro"}


def caminho_preferencias() -> Path:
    """Retorna uma pasta de configuração do usuário, sem misturar config ao banco."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "BARNS_Adega" / "settings.json"


def carregar_modo_tema(caminho: str | os.PathLike[str] | None = None) -> str:
    arquivo = Path(caminho) if caminho is not None else caminho_preferencias()
    try:
        dados: Any = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return MODO_PADRAO
    if isinstance(dados, dict) and dados.get("modo_tema") in MODOS_VALIDOS:
        return str(dados["modo_tema"])
    return MODO_PADRAO


def salvar_modo_tema(modo: str, caminho: str | os.PathLike[str] | None = None) -> Path:
    """Grava a escolha atomicamente para sobreviver a fechamentos inesperados."""
    if modo not in MODOS_VALIDOS:
        raise ValueError(f"Modo de tema inválido: {modo!r}")

    arquivo = Path(caminho) if caminho is not None else caminho_preferencias()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    try:
        dados: Any = json.loads(arquivo.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            dados = {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        dados = {}
    dados["modo_tema"] = modo

    descritor, nome_tmp = tempfile.mkstemp(prefix="settings_", suffix=".tmp", dir=str(arquivo.parent))
    try:
        with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as destino:
            json.dump(dados, destino, ensure_ascii=False, indent=2)
            destino.write("\n")
            destino.flush()
            os.fsync(destino.fileno())
        os.replace(nome_tmp, arquivo)
    except Exception:
        try:
            os.unlink(nome_tmp)
        except OSError:
            pass
        raise
    return arquivo
