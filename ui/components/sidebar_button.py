"""Botão real e navegável por teclado para a navegação principal."""
from __future__ import annotations

import customtkinter as ctk
from tkinter import TclError

from ui.theme import COR, RAIO_CARD
from ui.components.widgets import focar_controle


class SidebarButton(ctk.CTkButton):
    """Navegação com alvo de foco real, Enter/Espaço e setas para cima/baixo."""
    ICONES = {
        "vendas": "▣",
        "estoque": "▦",
        "banco": "▤",
        "historico": "◷",
        "pedidos": "☷",
        "resumo": "▥",
        "dias": "▣",
    }

    def __init__(self, master, icon_id, label_text, command):
        super().__init__(
            master,
            text=f"{self.ICONES.get(icon_id, '•')}    {label_text}",
            command=command,
            width=152,
            height=40,
            corner_radius=10,
            fg_color="transparent",
            hover_color=COR["hover"],
            text_color=COR["texto"],
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="normal"),
            border_width=0,
            anchor="w",
        )
        self.label_text = label_text
        self._normal_border = self.cget("border_color")
        self._normal_width = self.cget("border_width")
        self.bind("<FocusIn>", self._ao_focar, add="+")
        self.bind("<FocusOut>", self._ao_sair, add="+")
        self.bind("<Up>", lambda _e: self._focar_vizinho(-1), add="+")
        self.bind("<Down>", lambda _e: self._focar_vizinho(1), add="+")
        self.bind("<Right>", self._entrar_conteudo, add="+")
        canvas = getattr(self, "_canvas", None)
        if canvas is not None:
            canvas.configure(takefocus=1)
            canvas.bind("<Up>", lambda _e: self._focar_vizinho(-1), add="+")
            canvas.bind("<Down>", lambda _e: self._focar_vizinho(1), add="+")
            canvas.bind("<Right>", self._entrar_conteudo, add="+")

    def _ao_focar(self, _event=None):
        try:
            self.configure(border_width=2, border_color=COR["dourado"])
        except TclError:
            pass

    def _ao_sair(self, _event=None):
        try:
            self.configure(border_width=self._normal_width,
                           border_color=getattr(self, "_normal_border", COR["borda"]))
        except TclError:
            pass

    def _focar_vizinho(self, delta):
        botoes = getattr(self.master, "_nav_buttons", [])
        if not botoes:
            return "break"
        try:
            indice = botoes.index(self)
            focar_controle(botoes[(indice + delta) % len(botoes)])
        except (ValueError, TclError):
            pass
        return "break"

    def _entrar_conteudo(self, _event=None):
        app = getattr(self.master, "app", None)
        if app is not None:
            app.focar_conteudo()
        return "break"
