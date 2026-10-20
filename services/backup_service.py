"""Backup consistente SQLite com rotação e tratamento de locks no Windows."""
from __future__ import annotations

import logging
import os
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from infrastructure.database.connection import obter_caminho_banco

log = logging.getLogger(__name__)


def pasta_backups(db_path: str | None = None) -> Path:
    base = Path(db_path or obter_caminho_banco()).resolve()
    return base.parent / "backups"


def _substituir_com_retentativas(origem: Path, destino: Path, tentativas: int = 5) -> None:
    """Substitui o arquivo e tolera locks transitórios do Windows/antivírus."""
    for tentativa in range(tentativas):
        try:
            os.replace(origem, destino)
            return
        except PermissionError:
            if tentativa >= tentativas - 1:
                raise
            # Um antivírus ou indexador pode inspecionar brevemente o arquivo.
            time.sleep(0.15 * (tentativa + 1))


def criar_backup(db_path: str | None = None, max_backups: int = 14) -> Path | None:
    source_path = Path(db_path or obter_caminho_banco()).resolve()
    if not source_path.exists() or source_path.stat().st_size == 0:
        return None

    target_dir = pasta_backups(str(source_path))
    target_dir.mkdir(parents=True, exist_ok=True)

    # Microssegundos evitam colisões de nome em inicializações próximas.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target_path = target_dir / f"adega_{stamp}.db"
    # Nome temporário exclusivo evita que duas instâncias compartilhem o mesmo .tmp.
    tmp_path = target_dir / f".{target_path.name}.{uuid.uuid4().hex}.tmp"

    try:
        # Importante no Windows: o context manager nativo de sqlite3 faz commit/
        # rollback, mas NÃO fecha a conexão. closing() garante que os handles
        # estejam liberados antes de os.replace().
        with closing(sqlite3.connect(str(source_path), timeout=10.0)) as source:
            source.execute("PRAGMA busy_timeout = 10000")
            with closing(sqlite3.connect(str(tmp_path), timeout=10.0)) as target:
                source.backup(target)
                result = target.execute("PRAGMA integrity_check").fetchone()[0]
                if result != "ok":
                    raise sqlite3.DatabaseError(f"Integridade do backup inválida: {result}")
                target.commit()

        # As duas conexões já foram explicitamente fechadas aqui.
        _substituir_com_retentativas(tmp_path, target_path)

        backups = sorted(
            target_dir.glob("adega_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for obsolete in backups[max(1, max_backups):]:
            try:
                obsolete.unlink()
            except OSError:
                log.warning("Não foi possível remover backup antigo: %s", obsolete)

        log.info("Backup concluído: %s", target_path)
        return target_path
    except Exception:
        log.exception("Falha ao criar backup SQLite")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            log.warning("Não foi possível remover temporário de backup: %s", tmp_path)
        raise


def backup_se_preciso(db_path: str | None = None, intervalo_horas: int = 24) -> Path | None:
    source_path = Path(db_path or obter_caminho_banco()).resolve()
    if not source_path.exists():
        return None

    folder = pasta_backups(str(source_path))
    backups = (
        sorted(folder.glob("adega_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        if folder.exists()
        else []
    )
    if backups:
        ultimo = datetime.fromtimestamp(backups[0].stat().st_mtime)
        if datetime.now() - ultimo < timedelta(hours=intervalo_horas):
            return None

    return criar_backup(str(source_path))
