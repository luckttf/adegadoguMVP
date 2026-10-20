"""Histórico paginado e compacto de movimentações de estoque e auditoria."""
from __future__ import annotations

import math

import customtkinter as ctk
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO
from ui.components.calendar import SeletorData
from ui.components.page_header import construir_cabecalho


class PaginaHistorico(ctk.CTkFrame):
    TAMANHO_PAGINA = 30

    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        self.pagina = 0
        construir_cabecalho(
            self,
            "Histórico de movimentações",
            "Consulte entradas, saídas, aberturas de garrafa, perdas e ajustes registrados no sistema.",
        )

        topo = ctk.CTkFrame(
            self, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        topo.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            topo, text="Data da movimentação", text_color=COR["cinza"],
            font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(12, 8), pady=10)
        self.seletor_data = SeletorData(topo, on_change=self._alterar_filtro)
        self.seletor_data.pack(side="left", pady=8)
        ctk.CTkButton(
            topo, text="Atualizar", command=self._carregar, corner_radius=RAIO_BOTAO,
            fg_color=COR["azul"], hover_color=COR["azul_h"], width=100,
        ).pack(side="right", padx=10, pady=10)

        self.lbl_resultados = ctk.CTkLabel(
            self, text="", text_color=COR["cinza"], font=ctk.CTkFont(size=11), anchor="w",
        )
        self.lbl_resultados.pack(fill="x", padx=22, pady=(0, 4))

        # Controles fixos; a lista ocupa o espaço restante sem empurrar o rodapé.
        self.controles_paginacao = ctk.CTkFrame(self, fg_color="transparent")
        self.controles_paginacao.pack(side="bottom", fill="x", padx=20, pady=(4, 12))
        self.btn_anterior = ctk.CTkButton(
            self.controles_paginacao, text="← Anterior", width=112,
            command=lambda: self._mudar_pagina(-1), corner_radius=RAIO_BOTAO,
            fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"], border_width=1, border_color=COR["borda"],
        )
        self.btn_anterior.pack(side="left")
        self.lbl_pagina = ctk.CTkLabel(
            self.controles_paginacao, text="Página 1 de 1", text_color=COR["cinza"],
        )
        self.lbl_pagina.pack(side="left", expand=True)
        self.btn_proxima = ctk.CTkButton(
            self.controles_paginacao, text="Próxima →", width=112,
            command=lambda: self._mudar_pagina(1), corner_radius=RAIO_BOTAO,
            fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"], border_width=1, border_color=COR["borda"],
        )
        self.btn_proxima.pack(side="right")

        self.frame_hist = ctk.CTkScrollableFrame(self, fg_color=COR["fundo"])
        self.frame_hist.pack(fill="both", expand=True, padx=17, pady=(0, 4))
        self._carregar()

    def _alterar_filtro(self):
        self.pagina = 0
        self._carregar()

    def _mudar_pagina(self, delta: int):
        self.pagina = max(0, self.pagina + delta)
        self._carregar()

    def _atualizar_paginacao(self, total: int, total_paginas: int):
        inicio = self.pagina * self.TAMANHO_PAGINA + 1 if total else 0
        fim = min((self.pagina + 1) * self.TAMANHO_PAGINA, total)
        self.lbl_resultados.configure(
            text=f"Exibindo {inicio}–{fim} de {total} movimentação(ões) · 30 por página"
        )
        self.lbl_pagina.configure(text=f"Página {self.pagina + 1} de {total_paginas}")
        self.btn_anterior.configure(state="normal" if self.pagina > 0 else "disabled")
        self.btn_proxima.configure(state="normal" if self.pagina + 1 < total_paginas else "disabled")

    def _carregar(self):
        for widget in self.frame_hist.winfo_children():
            widget.destroy()

        cores_tipo = {
            "entrada": COR["verde"], "saida": COR["vermelho"],
            "abertura": COR["laranja"], "fechamento": COR["roxo"],
            "perda": COR["amarelo"], "ajuste": COR["azul"],
        }
        rotulos = {
            "entrada": "Entrada", "saida": "Saída", "abertura": "Abertura",
            "fechamento": "Fechamento", "perda": "Perda", "ajuste": "Ajuste",
        }
        data_filtro = self.seletor_data.get_data_str()
        total = database.contar_historico_completo(data=data_filtro)
        total_paginas = max(1, math.ceil(total / self.TAMANHO_PAGINA))
        self.pagina = min(self.pagina, total_paginas - 1)
        movs = database.buscar_historico_completo(
            data=data_filtro, limite=self.TAMANHO_PAGINA,
            offset=self.pagina * self.TAMANHO_PAGINA,
        )
        self._atualizar_paginacao(total, total_paginas)

        if not movs:
            ctk.CTkLabel(
                self.frame_hist,
                text="Nenhuma movimentação encontrada. Tente outra data ou limpe o filtro.",
                text_color=COR["cinza"], font=ctk.CTkFont(size=12),
            ).pack(pady=40)
            return

        for mov in movs:
            tipo = str(mov.get("tipo") or "outro").lower()
            cor = cores_tipo.get(tipo, COR["cinza"])
            # Uma linha compacta substitui os cartões altos anteriores, aumentando
            # a quantidade de eventos visíveis por tela sem eliminar informação.
            linha = ctk.CTkFrame(
                self.frame_hist, fg_color=COR["card"], corner_radius=9,
                border_width=1, border_color=COR["borda"], height=44,
            )
            linha.pack(fill="x", padx=3, pady=2)
            linha.pack_propagate(False)
            ctk.CTkFrame(linha, fg_color=cor, width=3, corner_radius=2).pack(
                side="left", fill="y", padx=(0, 9), pady=5,
            )
            ctk.CTkLabel(
                linha, text=mov.get("nome") or "Produto não identificado",
                font=ctk.CTkFont(size=11, weight="bold"), text_color=COR["texto"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)
            ctk.CTkLabel(
                linha, text=rotulos.get(tipo, tipo.replace("_", " ").title()),
                font=ctk.CTkFont(size=10, weight="bold"), text_color=cor,
                fg_color=COR["superficie"], corner_radius=6, padx=7, pady=3,
            ).pack(side="left", padx=(0, 8), pady=4)
            ctk.CTkLabel(
                linha, text=f"Qtd. {mov.get('quantidade', 0)}",
                font=ctk.CTkFont(size=10), text_color=COR["cinza"],
            ).pack(side="left", padx=(0, 12), pady=4)
            ctk.CTkLabel(
                linha, text=mov.get("data", "Data indisponível"),
                font=ctk.CTkFont(size=10), text_color=COR["cinza"],
            ).pack(side="right", padx=10, pady=4)

    def ao_mudar_tema(self):
        """Reconstrói apenas as linhas; o filtro e a página atual são preservados."""
        self._carregar()
