"""Componentes de interface e utilidades de acessibilidade/performance."""
from __future__ import annotations

import logging
import unicodedata
from typing import Optional
from collections.abc import Callable

import customtkinter as ctk
from tkinter import TclError

from ui.theme import COR, RAIO_BOTAO
from domain.autocomplete_rules import nome_base_sugestao, selecionar_sugestao

log = logging.getLogger(__name__)


def remover_acentos(txt: str | None) -> str:
    if not txt:
        return ""
    nfkd = unicodedata.normalize("NFKD", txt)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def debounce_widget(widget, callback: Callable[[], None], delay_ms: int = 140):
    """Adia uma operação de UI até o usuário parar de digitar por `delay_ms`."""
    state = {"after_id": None}

    def executar():
        state["after_id"] = None
        try:
            if widget.winfo_exists():
                callback()
        except TclError:
            # A tela pode ter sido fechada enquanto a chamada estava agendada.
            log.debug("Callback cancelado porque o widget já foi destruído", exc_info=True)

    def agendar(event=None):
        pending = state.get("after_id")
        if pending is not None:
            try:
                widget.after_cancel(pending)
            except TclError:
                pass
            state["after_id"] = None
        if event is not None and getattr(event, "keysym", "") in ("Return", "KP_Enter"):
            callback()
            return "break"
        try:
            state["after_id"] = widget.after(max(1, int(delay_ms)), executar)
        except TclError:
            state["after_id"] = None
        return None

    return agendar


def focar_controle(widget) -> None:
    """Move o foco para o alvo interativo real de um widget CustomTkinter."""
    try:
        alvo = getattr(widget, "_canvas", None) if isinstance(widget, ctk.CTkButton) else None
        (alvo or widget).focus_set()
    except (TclError, AttributeError):
        log.debug("Não foi possível focar o controle", exc_info=True)


def habilitar_foco_teclado(container) -> None:
    """Torna CTkButtons alcançáveis por Tab e ativáveis por Enter/Espaço.

    CustomTkinter desenha botões em um Canvas interno. Tornar esse Canvas
    focável permite usar a ordem natural de navegação do Tk; o anel de foco
    mantém o operador ciente do controle ativo.
    """
    def visitar(widget):
        try:
            if isinstance(widget, ctk.CTkButton):
                canvas = getattr(widget, "_canvas", None)
                if canvas is not None and not getattr(widget, "_barns_keyboard_ready", False):
                    try:
                        canvas.configure(takefocus=1)
                    except TclError:
                        log.debug("Não foi possível habilitar takefocus no botão", exc_info=True)

                    try:
                        border_width_original = widget.cget("border_width")
                        border_color_original = widget.cget("border_color")
                    except Exception:
                        border_width_original, border_color_original = 0, COR["borda"]
                    # A cor base é armazenada no widget para que a troca global de
                    # tema também atualize o valor restaurado ao perder o foco.
                    widget._barns_original_border_color = border_color_original
                    widget._barns_original_border_width = border_width_original

                    def ao_focar(_event, botao=widget):
                        try:
                            botao.configure(border_width=max(2, int(border_width_original or 0)),
                                            border_color=COR["dourado"])
                        except (TclError, ValueError):
                            pass

                    def ao_sair(_event, botao=widget):
                        try:
                            botao.configure(
                                border_width=getattr(botao, "_barns_original_border_width", border_width_original),
                                border_color=getattr(botao, "_barns_original_border_color", COR["borda"]),
                            )
                        except TclError:
                            pass

                    def ativar(_event, botao=widget):
                        try:
                            if str(botao.cget("state")) != "disabled":
                                botao.invoke()
                        except (TclError, AttributeError):
                            log.debug("Botão não pôde ser ativado pelo teclado", exc_info=True)
                        return "break"

                    canvas.bind("<FocusIn>", ao_focar, add="+")
                    canvas.bind("<FocusOut>", ao_sair, add="+")
                    canvas.bind("<Return>", ativar, add="+")
                    canvas.bind("<KP_Enter>", ativar, add="+")
                    canvas.bind("<space>", ativar, add="+")
                    widget._barns_keyboard_ready = True

            tipo_checkbox = getattr(ctk, "CTkCheckBox", None)
            if (tipo_checkbox is not None and isinstance(widget, tipo_checkbox)
                    and not getattr(widget, "_barns_checkbox_keyboard_ready", False)):
                canvas = getattr(widget, "_canvas", None)
                if canvas is not None:
                    try:
                        canvas.configure(takefocus=1)
                    except TclError:
                        log.debug("Não foi possível habilitar foco no checkbox", exc_info=True)

                    def checkbox_foco(_event, controle=widget):
                        try:
                            controle.configure(border_width=2, border_color=COR["dourado"])
                        except (TclError, TypeError):
                            pass

                    def checkbox_saiu(_event, controle=widget):
                        try:
                            controle.configure(border_width=1, border_color=COR["borda_azul"])
                        except (TclError, TypeError):
                            pass

                    def checkbox_ativar(_event, controle=widget):
                        try:
                            controle.toggle()
                        except (TclError, AttributeError):
                            log.debug("Checkbox não pôde ser alternado pelo teclado", exc_info=True)
                        return "break"

                    canvas.bind("<FocusIn>", checkbox_foco, add="+")
                    canvas.bind("<FocusOut>", checkbox_saiu, add="+")
                    canvas.bind("<space>", checkbox_ativar, add="+")
                    canvas.bind("<Return>", checkbox_ativar, add="+")
                    canvas.bind("<KP_Enter>", checkbox_ativar, add="+")
                    widget._barns_checkbox_keyboard_ready = True

            for child in widget.winfo_children():
                visitar(child)
        except TclError:
            # Widgets dinâmicos podem ser destruídos durante uma atualização.
            return

    visitar(container)


class StatusDot(ctk.CTkCanvas):
    """Indicador circular de status."""
    def __init__(self, master, cor, tamanho=12, **kwargs):
        super().__init__(master, width=tamanho, height=tamanho,
                         bg=COR["card"], highlightthickness=0, **kwargs)
        self.tamanho = tamanho
        self.set_cor(cor)

    def set_cor(self, cor):
        self.delete("all")
        pad = 1
        self.create_oval(pad, pad, self.tamanho - pad, self.tamanho - pad,
                         fill=cor, outline="")


class JanelaTrafficLights(ctk.CTkFrame):
    """Indicadores decorativos legados; serão revistos no redesign visual."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        for cor in (COR["vermelho"], COR["amarelo"], COR["verde"]):
            StatusDot(self, cor, tamanho=10).pack(side="left", padx=2)


class AutocompleteEntry(ctk.CTkFrame):
    """Campo com sugestões pesquisáveis por teclado e mouse."""
    def __init__(self, master, items_callback, on_enter_callback=None, max_items=8, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.items_callback = items_callback
        self.on_enter_callback = on_enter_callback
        self.max_items = max(1, int(max_items))
        self._sugestoes = []
        self._indice_selecionado = -1
        self._after_id = None
        self.entry_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self, textvariable=self.entry_var,
            placeholder_text="Digite para buscar...", height=38,
            fg_color=COR["input"], text_color=COR["texto"],
            border_color=COR["borda_azul"], corner_radius=RAIO_BOTAO,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.entry.pack(fill="x", expand=True)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<FocusOut>", self._agendar_fechar_se_fora)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<KP_Enter>", self._on_enter)
        self.entry.bind("<Down>", self._navegar_teclado)
        self.entry.bind("<Up>", self._navegar_teclado)
        self.entry.bind("<Escape>", self._escape)
        self.dropdown = None
        self._labels = []

    def get(self):
        return self.entry_var.get()

    def set(self, valor):
        self.entry_var.set(valor)
        self._cancelar_busca_agendada()
        self._fechar_sugestoes()

    def _cancelar_busca_agendada(self):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except TclError:
                pass
            self._after_id = None

    @staticmethod
    def _nome_base_sugestao(valor: str) -> str:
        return nome_base_sugestao(valor)

    def _texto_consulta(self) -> str:
        # Ao reusar o campo (ex.: no diálogo de movimentação), ele pode conter
        # uma sugestão já formatada. Pesquisar somente pelo nome evita buscas
        # literais por "Produto — preço".
        return self._nome_base_sugestao(self.entry_var.get())

    def _on_enter(self, event=None):
        """Confirma a sugestão pelo teclado, atualizando a busca antes de agir.

        Enter usa a opção destacada; sem destaque, prioriza correspondência
        exata e depois a primeira sugestão. Isso mantém o fluxo rápido de PDV,
        inclusive quando Enter é pressionado durante o debounce da pesquisa.
        """
        termo = self._texto_consulta()
        busca_pendente = self._after_id is not None
        sugestao_destacada = None
        if not busca_pendente and self._indice_selecionado >= 0 and self._indice_selecionado < len(self._sugestoes):
            sugestao_destacada = self._sugestoes[self._indice_selecionado]

        self._cancelar_busca_agendada()
        if not termo:
            self._fechar_sugestoes()
            return "break"

        try:
            itens = list(self.items_callback(termo) or [])[:self.max_items]
        except Exception:
            log.exception("Falha ao atualizar sugestões ao pressionar Enter")
            self._fechar_sugestoes()
            return "break"

        if not itens:
            self._fechar_sugestoes()
            return "break"

        escolhido = selecionar_sugestao(termo, itens, sugestao_destacada)
        if escolhido is None:
            self._fechar_sugestoes()
            return "break"

        self.entry_var.set(str(escolhido))
        self._fechar_sugestoes()
        if self.on_enter_callback:
            self.on_enter_callback()
        return "break"

    def _escape(self, _event=None):
        tinha_sugestoes = self.dropdown is not None or self._after_id is not None
        self._cancelar_busca_agendada()
        self._fechar_sugestoes()
        # Primeiro Escape fecha sugestões; sem sugestões, a tecla pode chegar
        # à janela principal e cancelar o carrinho conforme o atalho do PDV.
        return "break" if tinha_sugestoes else None

    def _navegar_teclado(self, event):
        if event.keysym not in ("Up", "Down"):
            return None
        if self._after_id is not None or not self.dropdown or not self._sugestoes:
            # Se a digitação ainda está dentro da janela de debounce, resolvemos
            # a consulta antes de navegar para não usar sugestões antigas.
            self._cancelar_busca_agendada()
            self._atualizar_sugestoes()
        if not self.dropdown or not self._sugestoes:
            return "break"
        if event.keysym == "Down":
            self._indice_selecionado = (self._indice_selecionado + 1) % len(self._sugestoes)
        else:
            self._indice_selecionado = (self._indice_selecionado - 1) % len(self._sugestoes)
        self._atualizar_destaque()
        return "break"

    def _atualizar_destaque(self):
        for i, lbl in enumerate(self._labels):
            lbl.configure(fg_color=COR["hover"] if i == self._indice_selecionado else "transparent")

    def _on_key_release(self, event=None):
        # [CORREÇÃO] Adicionado 'KP_Enter' para ignorar o Enter do teclado numérico e não refazer a busca.
        if event and event.keysym in ("Return", "KP_Enter", "Up", "Down", "Escape", "Tab", "Shift_L", "Shift_R"):
            return
        self._cancelar_busca_agendada()
        try:
            self._after_id = self.after(125, self._atualizar_sugestoes)
        except TclError:
            self._after_id = None
        return

    def _atualizar_sugestoes(self):
        self._after_id = None
        termo = self._texto_consulta()
        if not termo:
            self._fechar_sugestoes()
            return
        try:
            itens = list(self.items_callback(termo) or [])[:self.max_items]
        except Exception:
            log.exception("Falha ao buscar sugestões do autocomplete")
            self._fechar_sugestoes()
            return
        if itens:
            self._mostrar_sugestoes(itens)
        else:
            self._fechar_sugestoes()

    def _mostrar_sugestoes(self, itens):
        self._fechar_sugestoes()
        self._sugestoes = itens
        self._indice_selecionado = -1
        self.dropdown = ctk.CTkFrame(
            self.master, fg_color=COR["card"],
            border_width=1, border_color=COR["borda_azul"],
            corner_radius=RAIO_BOTAO
        )
        self.dropdown.place(in_=self.entry, x=0, rely=1.0, anchor="nw", relwidth=1.0)
        self._labels = []
        for item in itens:
            lbl = ctk.CTkLabel(self.dropdown, text=item, anchor="w",
                               fg_color="transparent", text_color=COR["texto"], cursor="hand2")
            lbl.pack(fill="x", padx=8, pady=4)
            lbl.bind("<Button-1>", lambda _e, val=item: self._selecionar_e_confirmar(val))
            lbl.bind("<Enter>", lambda _e, idx=len(self._labels): self._destacar(idx))
            self._labels.append(lbl)

    def _destacar(self, idx):
        self._indice_selecionado = idx
        self._atualizar_destaque()

    def _selecionar_e_confirmar(self, valor):
        self._selecionar(valor)
        if self.on_enter_callback:
            self.on_enter_callback()

    def _selecionar(self, valor):
        self.entry_var.set(valor)
        self._fechar_sugestoes()

    def _agendar_fechar_se_fora(self, _event=None):
        try:
            self.after_idle(self._fechar_se_foco_fora)
        except TclError:
            pass

    def _fechar_se_foco_fora(self):
        try:
            foco = self.focus_get()
        except TclError:
            foco = None
        if foco is self.entry:
            return
        atual = foco
        while atual is not None:
            if atual is self.dropdown:
                return
            atual = getattr(atual, "master", None)
        self._fechar_sugestoes()

    def _fechar_sugestoes(self, event=None):
        if self.dropdown:
            try:
                self.dropdown.destroy()
            except TclError:
                pass
        self.dropdown = None
        self._sugestoes = []
        self._labels = []
        self._indice_selecionado = -1

    def get_selected_product_name(self):
        return self._nome_base_sugestao(self.entry_var.get())

    def destroy(self):
        self._cancelar_busca_agendada()
        self._fechar_sugestoes()
        super().destroy()