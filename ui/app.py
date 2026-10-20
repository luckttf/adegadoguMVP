"""Janela principal BARNS: carregamento sob demanda e navegação acessível."""
from __future__ import annotations

import logging

import customtkinter as ctk
from tkinter import messagebox, TclError

from infrastructure.database.connection import obter_caminho_banco
from services.backup_service import backup_se_preciso
from ui.theme import COR, aplicar_tema
from ui.components.widgets import habilitar_foco_teclado, focar_controle
from ui.sidebar import BarraLateral
from ui.pages.sales import PaginaVendas
from ui.pages.inventory import PaginaEstoque
from ui.pages.catalog import PaginaBanco
from ui.pages.history import PaginaHistorico
from ui.pages.orders import PaginaPedidos
from ui.pages.reports import PaginaResumo
from ui.pages.operation_days import PaginaDias

log = logging.getLogger(__name__)


class AdegaApp(ctk.CTk):
    PAGINAS = ("Vendas", "Estoque", "Banco", "Histórico", "Pedidos", "Resumo", "Dias")
    ATUALIZADORES = {
        "Vendas": "_recarregar_produtos",
        "Estoque": "atualizar_lista",
        "Banco": "atualizar_lista",
        "Histórico": "_carregar",
        "Pedidos": "_carregar",
        "Resumo": "_carregar",
        "Dias": "_carregar",
    }

    def __init__(self):
        super().__init__()
        self.title("BARNS Adega")
        self.geometry("1440x860")
        self.minsize(1100, 680)
        self.configure(fg_color=COR["fundo"])

        self.container = ctk.CTkFrame(self, fg_color=COR["fundo"], corner_radius=0)
        self.container.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)

        # As páginas são instanciadas somente na primeira visita. Isso evita
        # consultar e desenhar todo o histórico antes de o operador abrir a tela.
        self._factories = {
            "Vendas": PaginaVendas,
            "Estoque": PaginaEstoque,
            "Banco": PaginaBanco,
            "Histórico": PaginaHistorico,
            "Pedidos": PaginaPedidos,
            "Resumo": PaginaResumo,
            "Dias": PaginaDias,
        }
        self.paginas: dict[str, ctk.CTkFrame] = {}
        self.pagina_atual = None
        self._pagina_atual_nome: str | None = None

        self.barra = BarraLateral(self, self)
        self._configurar_atalhos()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self.mostrar_pagina("Vendas")
        self.after(24 * 60 * 60 * 1000, self._backup_periodico)

    def _obter_pagina(self, nome: str):
        pagina = self.paginas.get(nome)
        if pagina is None:
            fabrica = self._factories[nome]
            pagina = fabrica(self.container, self)
            self.paginas[nome] = pagina
            habilitar_foco_teclado(pagina)
        return pagina

    # Propriedades mantêm compatibilidade com chamadas antigas entre páginas.
    @property
    def pagina_vendas(self):
        return self._obter_pagina("Vendas")

    @property
    def pagina_estoque(self):
        return self._obter_pagina("Estoque")

    @property
    def pagina_banco(self):
        return self._obter_pagina("Banco")

    @property
    def pagina_historico(self):
        return self._obter_pagina("Histórico")

    @property
    def pagina_pedidos(self):
        return self._obter_pagina("Pedidos")

    @property
    def pagina_resumo(self):
        return self._obter_pagina("Resumo")

    @property
    def pagina_dias(self):
        return self._obter_pagina("Dias")

    def mostrar_pagina(self, nome: str):
        if nome not in self._factories:
            log.warning("Tentativa de navegação para página desconhecida: %s", nome)
            return

        mesma_pagina = self._pagina_atual_nome == nome
        if self.pagina_atual is not None and not mesma_pagina:
            self.pagina_atual.pack_forget()

        existente = nome in self.paginas
        pagina = self._obter_pagina(nome)
        self._pagina_atual_nome = nome
        self.pagina_atual = pagina
        if not pagina.winfo_manager():
            pagina.pack(fill="both", expand=True)
        if existente and not mesma_pagina:
            # Páginas ocultas podem ficar desatualizadas; atualize ao reabri-las.
            # Clicar de novo na página atual não deve reconstruir a lista inteira.
            self._atualizar_pagina(nome)

        self._atualizar_estado_navegacao()
        habilitar_foco_teclado(pagina)

    def alternar_tema(self, modo_noturno: bool):
        """Alterna o tema global sem destruir telas, estado do carrinho ou foco."""
        modo = "escuro" if modo_noturno else "claro"
        try:
            salvo = aplicar_tema(self, modo)
            self._atualizar_estado_navegacao()
            self._atualizar_conteudo_apos_tema()
            self._atualizar_estado_navegacao()
            if not salvo:
                messagebox.showwarning(
                    "Preferência não salva",
                    "O tema foi alterado nesta sessão, mas não foi possível salvar a preferência. "
                    "Verifique a permissão da pasta de configuração do usuário.",
                    parent=self,
                )
            log.info("Tema alterado para %s", modo)
            return salvo
        except Exception as exc:
            log.exception("Falha ao aplicar tema %s", modo)
            messagebox.showerror(
                "Não foi possível alterar o tema",
                "O aplicativo não conseguiu aplicar a nova aparência. Consulte barns.log.\n\n" + str(exc),
                parent=self,
            )
            # Tenta devolver a checkbox ao tema atualmente ativo sem disparar seu callback.
            try:
                self.barra.var_modo_noturno.set(not modo_noturno)
            except Exception:
                pass
            return False

    def _atualizar_conteudo_apos_tema(self):
        """Atualiza só o conteúdo visível após a troca, evitando trabalho em lote.

        A troca de cores recursa por todas as páginas já criadas. A página atual
        é redesenhada para não deixar linhas antigas com superfícies internas
        incompatíveis; páginas ocultas já são atualizadas ao serem reabertas por
        ``mostrar_pagina``. O estado dos formulários e o carrinho permanecem.
        """
        nome = self._pagina_atual_nome
        pagina = self.paginas.get(nome) if nome else None
        if pagina is None:
            return

        restaurar = []
        pendentes = list(pagina.winfo_children())
        while pendentes:
            widget = pendentes.pop()
            try:
                pendentes.extend(widget.winfo_children())
            except Exception:
                pass
            canvas = getattr(widget, "_parent_canvas", None)
            if canvas is not None:
                try:
                    restaurar.append((canvas, float(canvas.yview()[0])))
                except Exception:
                    pass

        atualizadores = {
            "Vendas": "_renderizar_carrinho",
            "Estoque": "atualizar_lista",
            "Banco": "atualizar_lista",
            "Histórico": "ao_mudar_tema",
            "Pedidos": "_carregar",
            "Resumo": "_carregar",
            "Dias": "ao_mudar_tema",
        }
        metodo = atualizadores.get(nome)
        try:
            if metodo:
                getattr(pagina, metodo)()
            habilitar_foco_teclado(pagina)
        except Exception:
            log.exception("Falha ao atualizar a página %s após troca de tema", nome)
        for canvas, fracao in restaurar:
            try:
                self.after_idle(lambda c=canvas, f=fracao: c.yview_moveto(f) if c.winfo_exists() else None)
            except Exception:
                log.debug("Não foi possível restaurar a posição de rolagem", exc_info=True)

    def _atualizar_estado_navegacao(self):
        botoes = getattr(self.barra, "_botoes_por_nome", {})
        for nome, botao in botoes.items():
            try:
                selecionado = nome == self._pagina_atual_nome
                botao.configure(
                    fg_color=COR["hover"] if selecionado else "transparent",
                    text_color=COR["dourado"] if selecionado else COR["texto"],
                )
            except TclError:
                log.debug("Botão de navegação já destruído", exc_info=True)

    def _atualizar_pagina(self, nome: str):
        pagina = self.paginas.get(nome)
        if pagina is None:
            return
        metodo = self.ATUALIZADORES.get(nome)
        if metodo:
            try:
                getattr(pagina, metodo)()
                habilitar_foco_teclado(pagina)
            except Exception:
                log.exception("Falha ao atualizar a página %s", nome)

    def atualizar_todas_abas(self):
        """Atualiza somente a tela visível; as outras carregam ao serem abertas."""
        if self._pagina_atual_nome:
            self._atualizar_pagina(self._pagina_atual_nome)
        try:
            self.barra._atualizar_status_dia()
        except Exception:
            log.exception("Falha ao atualizar o status do dia de operação")

    def _configurar_atalhos(self):
        # Atalhos numéricos: navegação rápida sem depender exclusivamente do mouse.
        for numero, nome in enumerate(self.PAGINAS, start=1):
            self.bind(f"<Control-Key-{numero}>",
                      lambda _e, destino=nome: self._atalho_pagina(destino), add="+")
        self.bind("<F6>", self._alternar_foco, add="+")
        self.bind("<Alt-Left>", lambda _e: self._navegar_pagina(-1), add="+")
        self.bind("<Alt-Right>", lambda _e: self._navegar_pagina(1), add="+")
        self.bind("<F12>", lambda _e: self._atalho_venda("finalizado"), add="+")
        self.bind("<F2>", lambda _e: self._atalho_venda("pendente"), add="+")
        self.bind("<Escape>", self._atalho_escape, add="+")

    def _atalho_pagina(self, nome: str):
        self.mostrar_pagina(nome)
        self.after_idle(self.focar_conteudo)
        return "break"

    def _navegar_pagina(self, delta: int):
        atual = self._pagina_atual_nome or "Vendas"
        indice = self.PAGINAS.index(atual)
        destino = self.PAGINAS[(indice + delta) % len(self.PAGINAS)]
        self.mostrar_pagina(destino)
        self.after_idle(self.focar_conteudo)
        return "break"

    def _atalho_venda(self, status: str):
        if self._pagina_atual_nome == "Vendas":
            self.paginas["Vendas"]._finalizar(status)
            return "break"
        return None

    def _atalho_escape(self, _event=None):
        if self._pagina_atual_nome == "Vendas":
            pagina = self.paginas.get("Vendas")
            foco = self.focus_get()
            # No campo de busca, o autocomplete fecha o dropdown primeiro.
            if foco is getattr(getattr(pagina, "autocomplete", None), "entry", None):
                if getattr(pagina.autocomplete, "dropdown", None):
                    pagina.autocomplete._escape()
                    return "break"
            pagina._cancelar()
            return "break"
        return None

    def _esta_na_barra(self, widget) -> bool:
        atual = widget
        while atual is not None:
            if atual is self.barra:
                return True
            atual = getattr(atual, "master", None)
        return False

    def _alternar_foco(self, _event=None):
        foco = self.focus_get()
        if foco is not None and self._esta_na_barra(foco):
            self.focar_conteudo()
        else:
            botoes = getattr(self.barra, "_botoes_por_nome", {})
            botao = botoes.get(self._pagina_atual_nome)
            if botao is not None:
                focar_controle(botao)
        return "break"

    def focar_conteudo(self):
        pagina = self.pagina_atual
        if pagina is None:
            return "break"
        if self._pagina_atual_nome == "Vendas":
            campo = getattr(getattr(pagina, "autocomplete", None), "entry", None)
            if campo is not None:
                campo.focus_set()
                return "break"

        tipos = tuple(
            tipo for tipo in (
                getattr(ctk, "CTkEntry", None), getattr(ctk, "CTkButton", None),
                getattr(ctk, "CTkComboBox", None), getattr(ctk, "CTkCheckBox", None),
                getattr(ctk, "CTkOptionMenu", None), getattr(ctk, "CTkTextbox", None),
            ) if isinstance(tipo, type)
        )

        def procurar(widget):
            for filho in widget.winfo_children():
                if tipos and isinstance(filho, tipos):
                    try:
                        if str(filho.cget("state")) != "disabled":
                            return filho
                    except Exception:
                        return filho
                encontrado = procurar(filho)
                if encontrado is not None:
                    return encontrado
            return None

        primeiro = procurar(pagina)
        if primeiro is not None:
            focar_controle(primeiro)
        return "break"

    def _ao_fechar(self):
        log.info("Encerrando BARNS Adega pela ação do operador.")
        try:
            self.destroy()
        except TclError:
            pass

    def _backup_periodico(self):
        """Backup periódico sem encerrar o PDV em caso de falha."""
        try:
            destino = backup_se_preciso(obter_caminho_banco(), intervalo_horas=24)
            if destino:
                log.info("Backup periódico concluído: %s", destino)
        except Exception:
            log.exception("Falha no backup automático do BARNS")
            try:
                messagebox.showwarning(
                    "Falha no backup automático",
                    "Não foi possível concluir o backup automático.\n"
                    "O sistema continuará aberto; verifique a pasta de backups e o arquivo barns.log.",
                    parent=self,
                )
            except TclError:
                pass
        finally:
            try:
                if self.winfo_exists():
                    self.after(24 * 60 * 60 * 1000, self._backup_periodico)
            except TclError:
                pass
