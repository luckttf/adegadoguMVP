"""Conexões SQLite, com espera por lock e caminho compatível com a versão anterior."""
import os
import sys
import sqlite3
import unicodedata
from contextlib import contextmanager
from typing import Optional


def remover_acentos(txt: Optional[str]) -> str:
    if not txt:
        return ""
    nfkd = unicodedata.normalize("NFKD", txt)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def obter_caminho_banco() -> str:
    configurado = os.environ.get("BARNS_DB_PATH")
    if configurado:
        return os.path.abspath(os.path.expanduser(configurado))
    diretorio = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(diretorio, "adega_dados.db")


def conectar() -> sqlite3.Connection:
    caminho = obter_caminho_banco()
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    conn = sqlite3.connect(caminho, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.create_function("unaccent", 1, remover_acentos)
    return conn


@contextmanager
def get_db():
    """Abre uma transação, faz commit somente no sucesso e rollback em falha."""
    conn = conectar()
    try:
        yield conn, conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
