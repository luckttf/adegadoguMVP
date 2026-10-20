"""Ponto de entrada da aplicação BARNS Adega."""
import logging
from pathlib import Path
from tkinter import messagebox
from database import criar_tabelas
from infrastructure.database.connection import obter_caminho_banco
from services.backup_service import backup_se_preciso, criar_backup
from ui.app import AdegaApp


def main() -> int:
    caminho_banco = obter_caminho_banco()
    caminho_log = str(Path(caminho_banco).with_name("barns.log"))
    logging.basicConfig(filename=caminho_log, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    
    backup_falhou = False
    
    try:
        # [CORREÇÃO] O backup inicial agora é tolerante a falhas para não impedir a abertura do app.
        if Path(caminho_banco).is_file() and Path(caminho_banco).stat().st_size > 0:
            try:
                criar_backup(caminho_banco)
            except Exception:
                logging.exception("Falha ao criar backup pré-inicialização. O app continuará aberto.")
                backup_falhou = True
                
        criar_tabelas()
        
        try:
            backup_se_preciso(caminho_banco, intervalo_horas=24)
        except Exception:
            logging.exception("Falha ao verificar backup periódico. O app continuará aberto.")
            backup_falhou = True

        logging.info("Inicializando janela principal do BARNS Adega.")
        app = AdegaApp()
        
        if backup_falhou:
            # Exibe o aviso de forma não bloqueante após a janela principal carregar
            app.after(500, lambda: messagebox.showwarning(
                "Aviso de Backup", 
                "Não foi possível criar o backup automático na inicialização. "
                "O sistema continuará aberto, mas verifique o espaço em disco e o arquivo barns.log.",
                parent=app
            ))
            
        logging.info("Janela criada; entrando no loop de eventos do Tk.")
        app.mainloop()
        logging.info("Loop de eventos encerrado; aplicação finalizada.")
        return 0
    except Exception:
        logging.exception("Falha fatal ao iniciar o BARNS Adega")
        raise


if __name__ == "__main__":
    raise SystemExit(main())