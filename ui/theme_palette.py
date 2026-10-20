"""Paletas e utilidades puras de cores para o tema BARNS.

Este módulo não depende do Tkinter, permitindo validar a paleta em testes
headless e manter a lógica de mapeamento separada da interface gráfica.
"""
from __future__ import annotations

from typing import Any, Mapping

PALETAS: dict[str, dict[str, str]] = {
    "claro": {
        "fundo": "#F5F5F7",
        "card": "#FFFFFF",
        "superficie": "#F9F9FB",
        "input": "#F0F0F5",
        "hover": "#F4E8ED",
        "texto": "#1D1D1F",
        # Cores semânticas próprias evitam mapear texto de marca para a cor de cartão.
        "texto_sobre_marca": "#FFFAFC",
        "texto_sobre_alerta": "#FFF8E8",
        "cinza": "#626269",
        "verde": "#238653",
        "verde_h": "#196B42",
        "azul": "#8C3155",
        "azul_h": "#702642",
        "vermelho": "#C2394B",
        "vermelho_h": "#A42B3C",
        "amarelo": "#8A5A00",
        "laranja": "#A94E24",
        "roxo": "#76506D",
        "vinho": "#8C3155",
        "vinho_h": "#702642",
        "dourado": "#80551F",
        "borda": "#E2E2E8",
        "borda_azul": "#D8B7C4",
        "borda_verde": "#C7E1D2",
        "borda_vinho": "#E0C5CF",
    },
    "escuro": {
        "fundo": "#0B0E14",
        "card": "#141923",
        "superficie": "#191F2B",
        "input": "#202735",
        "hover": "#1A2B42",
        "texto": "#F2F5FA",
        "texto_sobre_marca": "#F8FBFF",
        "texto_sobre_alerta": "#1C2533",
        "cinza": "#A8B2C3",
        "verde": "#45C982",
        "verde_h": "#269E61",
        "azul": "#4C9AFF",
        "azul_h": "#2F7DD8",
        "vermelho": "#FF697D",
        "vermelho_h": "#D94B60",
        "amarelo": "#F2C66D",
        "laranja": "#FFA06A",
        "roxo": "#8BAEFF",
        "vinho": "#4C9AFF",
        "vinho_h": "#2F7DD8",
        "dourado": "#82BAFF",
        "borda": "#2C3545",
        "borda_azul": "#345C8A",
        "borda_verde": "#2A5B47",
        # Deve ser distinto de borda_azul: a troca de tema mapeia cores antigas
        # para novas, e dois papéis visuais com destinos diferentes não podem
        # compartilhar o mesmo valor de origem.
        "borda_vinho": "#3D526F",
    },
}


def criar_mapa_cores(atual: Mapping[str, str], destino: Mapping[str, str]) -> dict[str, str]:
    """Cria um mapa de cor antiga -> cor nova, rejeitando colisões ambíguas."""
    if set(atual) != set(destino):
        raise ValueError("As paletas devem possuir exatamente as mesmas chaves.")

    mapa: dict[str, str] = {}
    for chave, cor_antiga in atual.items():
        origem = cor_antiga.lower()
        nova = destino[chave]
        existente = mapa.get(origem)
        if existente is not None and existente.lower() != nova.lower():
            raise ValueError(
                f"A cor {cor_antiga!r} representa mais de um papel visual com destinos diferentes."
            )
        mapa[origem] = nova
    return mapa


def substituir_cor(valor: Any, mapa: Mapping[str, str]) -> Any:
    """Mapeia strings e pares de cores sem modificar valores não reconhecidos."""
    if isinstance(valor, str):
        return mapa.get(valor.lower(), valor)
    if isinstance(valor, tuple):
        convertido = tuple(substituir_cor(parte, mapa) for parte in valor)
        return convertido if convertido != valor else valor
    if isinstance(valor, list):
        convertido = [substituir_cor(parte, mapa) for parte in valor]
        return convertido if convertido != valor else valor
    return valor
