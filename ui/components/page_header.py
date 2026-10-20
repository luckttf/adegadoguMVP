"""Cabeçalhos padronizados para as páginas do BARNS."""
from __future__ import annotations

import customtkinter as ctk
from ui.theme import COR


def construir_cabecalho(master, titulo: str, descricao: str) -> ctk.CTkFrame:
    """Cria um cabeçalho leve, reutilizável e compatível com o tema dinâmico."""
    frame = ctk.CTkFrame(master, fg_color="transparent", corner_radius=0)
    frame.pack(fill="x", padx=20, pady=(18, 8))

    ctk.CTkLabel(
        frame,
        text=titulo,
        font=ctk.CTkFont(size=23, weight="bold"),
        text_color=COR["texto"],
        anchor="w",
    ).pack(anchor="w")
    ctk.CTkLabel(
        frame,
        text=descricao,
        font=ctk.CTkFont(size=11),
        text_color=COR["cinza"],
        anchor="w",
        justify="left",
        wraplength=1000,
    ).pack(anchor="w", pady=(3, 0))
    return frame
