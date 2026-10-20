"""Tema dinâmico claro/escuro BARNS, com persistência e troca sem recriar telas."""
from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk
from tkinter import TclError

from ui.theme_palette import PALETAS, criar_mapa_cores, substituir_cor
from ui.theme_preferences import carregar_modo_tema, salvar_modo_tema

log = logging.getLogger(__name__)
FONTE = "Segoe UI"
FONTE_MONO = "Cascadia Mono"
MODO_TEMA = carregar_modo_tema()
COR = dict(PALETAS[MODO_TEMA])

# O modo é aplicado antes da criação da primeira janela. A cor explícita dos
# componentes vem de COR; set_appearance_mode também atualiza partes nativas
# internas do CustomTkinter que utilizem cores sensíveis ao modo.
ctk.set_appearance_mode("dark" if MODO_TEMA == "escuro" else "light")
ctk.set_default_color_theme("blue")

RAIO_CARD = 14
RAIO_BOTAO = 9
ESPACO = 8

_OPCOES_DE_COR = (
    "fg_color", "bg_color", "text_color", "border_color", "hover_color", "button_color",
    "button_hover_color", "scrollbar_button_color", "scrollbar_button_hover_color",
    "progress_color", "placeholder_text_color", "checkmark_color", "dropdown_fg_color",
    "dropdown_hover_color", "dropdown_text_color", "selected_color", "selected_hover_color",
    "text_color_disabled", "scrollbar_fg_color", "label_fg_color", "label_text_color",
    "bg", "background", "fg", "highlightbackground",
    "highlightcolor", "insertbackground",
)
_OPCOES_DE_ITEM_CANVAS = ("fill", "outline", "activefill", "disabledfill")


def _fundo_efetivo(widget: Any) -> str | None:
    """Resolve a superfície visível subindo a hierarquia se houver transparência."""
    atual = widget
    while atual is not None:
        for opcao in ("fg_color", "bg_color", "background", "bg"):
            try:
                valor = atual.cget(opcao)
            except Exception:
                continue
            if isinstance(valor, str) and valor.lower() == "transparent":
                continue
            if valor in (None, ""):
                continue
            try:
                aplicado = atual._apply_appearance_mode(valor)
                if isinstance(aplicado, str) and aplicado.lower() != "transparent":
                    return aplicado
            except Exception:
                if isinstance(valor, str) and valor.startswith("#"):
                    return valor
        atual = getattr(atual, "master", None)
    return None


def _sincronizar_canvas_scrollavel(widget: Any) -> None:
    """Corrige o canvas Tk interno de CTkScrollableFrame após trocar a paleta.

    O frame externo pode mudar de cor sem que a superfície Tk interna acompanhe
    todos os temas/versões do CustomTkinter. A atualização é defensiva porque os
    atributos internos podem variar entre versões.
    """
    canvas = getattr(widget, "_parent_canvas", None)
    if canvas is None:
        return
    try:
        cor_propria = widget.cget("fg_color")
    except Exception:
        cor_propria = None
    alvo = widget.master if isinstance(cor_propria, str) and cor_propria.lower() == "transparent" else widget
    fundo = _fundo_efetivo(alvo)
    if fundo:
        try:
            canvas.configure(bg=fundo, highlightthickness=0)
        except (TclError, ValueError, TypeError):
            log.debug("Não foi possível sincronizar fundo do canvas rolável", exc_info=True)


def _mapear_widget(widget: Any, mapa: dict[str, str]) -> None:
    """Atualiza cores de um widget existente; trata Canvas e widgets destruídos."""
    # Alguns auxiliares de foco guardam a cor base para restaurá-la no FocusOut.
    # Atualizamos também esses atributos para não reintroduzir a paleta anterior.
    for atributo in ("_barns_original_border_color", "_normal_border"):
        try:
            valor = getattr(widget, atributo)
            convertido = substituir_cor(valor, mapa)
            if convertido != valor:
                setattr(widget, atributo, convertido)
        except Exception:
            pass

    for opcao in _OPCOES_DE_COR:
        try:
            atual = widget.cget(opcao)
            novo = substituir_cor(atual, mapa)
            if novo != atual:
                widget.configure(**{opcao: novo})
        except (TclError, ValueError, TypeError, KeyError):
            # Cada família de widget expõe um subconjunto diferente de opções.
            continue
        except Exception:
            log.debug("Não foi possível atualizar a opção visual %s", opcao, exc_info=True)

    # Os gráficos e indicadores são desenhos de Canvas, não widgets separados.
    try:
        itens = widget.find_all()
    except Exception:
        itens = ()
    for item in itens:
        for opcao in _OPCOES_DE_ITEM_CANVAS:
            try:
                atual = widget.itemcget(item, opcao)
                novo = substituir_cor(atual, mapa)
                if novo != atual:
                    widget.itemconfigure(item, **{opcao: novo})
            except (TclError, ValueError, TypeError, KeyError):
                continue
            except Exception:
                log.debug("Não foi possível atualizar cor de item Canvas", exc_info=True)

    if hasattr(widget, "_parent_canvas"):
        _sincronizar_canvas_scrollavel(widget)

    try:
        filhos = widget.winfo_children()
    except (TclError, AttributeError):
        return
    for filho in filhos:
        _mapear_widget(filho, mapa)


def aplicar_tema(root: Any, modo: str) -> bool:
    """Aplica tema aos widgets existentes sem recriá-los nem perder o carrinho.

    Retorna True se a preferência foi persistida. Mesmo se a pasta de configuração
    estiver indisponível, o tema é aplicado para a sessão atual e o erro é logado.
    """
    global MODO_TEMA
    if modo not in PALETAS:
        raise ValueError(f"Modo de tema inválido: {modo!r}")

    paleta_nova = PALETAS[modo]
    mapa = criar_mapa_cores(COR, paleta_nova)
    COR.clear()
    COR.update(paleta_nova)
    MODO_TEMA = modo
    ctk.set_appearance_mode("dark" if modo == "escuro" else "light")
    _mapear_widget(root, mapa)

    try:
        salvar_modo_tema(modo)
        return True
    except OSError:
        log.exception("Tema alterado para esta sessão, mas não foi possível salvar a preferência.")
        return False


def modo_noturno_ativo() -> bool:
    return MODO_TEMA == "escuro"
