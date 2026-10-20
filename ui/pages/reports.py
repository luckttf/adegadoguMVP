"""Resumo financeiro do dia operacional atualmente aberto."""
from __future__ import annotations

import customtkinter as ctk
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO
from ui.components.page_header import construir_cabecalho


class PaginaResumo(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        self._visivel = True

        construir_cabecalho(
            self,
            "Resumo financeiro",
            "Visão operacional do dia aberto: vendas entregues, recebimentos, descontos, fiado e lucro estimado.",
        )

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkButton(
            barra, text="Atualizar", width=100, corner_radius=RAIO_BOTAO,
            command=self._carregar, fg_color=COR["azul"], hover_color=COR["azul_h"],
        ).pack(side="right")
        self.btn_olho = ctk.CTkButton(
            barra, text="Ocultar valores", width=130, corner_radius=RAIO_BOTAO,
            command=self._alternar, fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"], border_width=1, border_color=COR["borda"],
        )
        self.btn_olho.pack(side="right", padx=(0, 8))

        self.frame_cards = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_cards.pack(fill="x", padx=17, pady=(4, 8))
        for coluna in range(4):
            self.frame_cards.grid_columnconfigure(coluna, weight=1, uniform="metricas")

        grafico_card = ctk.CTkFrame(
            self, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        grafico_card.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            grafico_card, text="Recebimentos por meio de pagamento",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COR["texto"], anchor="w",
        ).pack(anchor="w", padx=14, pady=(10, 0))
        self.canvas = ctk.CTkCanvas(
            grafico_card, height=180, bg=COR["card"], highlightthickness=0,
        )
        self.canvas.pack(fill="x", padx=8, pady=(0, 8))

        self.container = ctk.CTkScrollableFrame(
            self, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        self.container.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        self._carregar()

    def _alternar(self):
        self._visivel = not self._visivel
        self.btn_olho.configure(text="Mostrar valores" if not self._visivel else "Ocultar valores")
        self._carregar()

    def _fmt(self, valor):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if self._visivel else "R$ ••••••"

    def _desenhar_grafico(self, dados):
        self.canvas.delete("all")
        agg = {}
        for linha in dados:
            if linha.get("status") != "finalizado":
                continue
            forma = linha.get("forma_pagamento") or "Não informado"
            agg[forma] = agg.get(forma, 0) + float(linha.get("total_liquido") or 0)
        if not agg:
            largura = max(self.canvas.winfo_width(), 520)
            self.canvas.create_text(
                largura / 2, 82, text="Nenhum recebimento registrado neste dia.",
                fill=COR["cinza"], font=("Segoe UI", 11),
            )
            return
        formas = list(agg.keys())
        valores = [agg[f] for f in formas]
        max_val = max(valores) if valores else 1
        largura = max(self.canvas.winfo_width(), 600)
        espacamento = max(100, (largura - 80) // max(1, len(formas)))
        largura_barra = min(54, max(24, espacamento // 3))
        x0 = 40
        y_base = 145
        altura_max = 98
        for i, (forma, val) in enumerate(zip(formas, valores)):
            altura = int((val / max_val) * altura_max) if max_val > 0 else 0
            x1 = x0 + i * espacamento
            y1 = y_base - altura
            self.canvas.create_rectangle(
                x1, y1, x1 + largura_barra, y_base,
                fill=COR["azul"], outline="", width=0,
            )
            self.canvas.create_text(
                x1 + largura_barra / 2, y_base + 16, text=forma,
                fill=COR["cinza"], font=("Segoe UI", 9),
            )
            self.canvas.create_text(
                x1 + largura_barra / 2, max(10, y1 - 10),
                text=self._fmt(val) if self._visivel else "•••",
                fill=COR["texto"], font=("Segoe UI", 9, "bold"),
            )

    def _mensagem(self, texto: str, cor: str | None = None):
        ctk.CTkLabel(
            self.container, text=texto, text_color=cor or COR["cinza"],
            font=ctk.CTkFont(size=12), anchor="w", justify="left",
        ).pack(fill="x", padx=12, pady=14)

    def _carregar(self):
        for w in self.frame_cards.winfo_children():
            w.destroy()
        for w in self.container.winfo_children():
            w.destroy()
        self.canvas.delete("all")

        dia = database.obter_dia_aberto()
        if not dia:
            self._mensagem("Nenhum dia de operação aberto. Inicie um dia para acompanhar os indicadores.", COR["amarelo"])
            self._desenhar_grafico([])
            return

        info, linhas = database.obter_resumo_dia_operacao(dia["id"])
        pagamentos_dia = database.obter_resumo_pagamentos_dia(dia["id"])
        # Pode haver recebimento de fiado antigo ou saldo de fiado sem vendas novas neste dia.
        total_fiado = database.obter_total_fiado_aberto()
        
        # [CORREÇÃO] Variável 'fiados_abertos' não existia, causava NameError. Trocado por 'total_fiado'.
        if not linhas and not pagamentos_dia and not total_fiado:
            self._mensagem("Nenhuma venda, recebimento ou fiado em aberto neste momento.")
            self._desenhar_grafico([])
            return

        total_bruto = sum(float(l.get("total_bruto") or 0) for l in linhas)
        total_desc = sum(float(l.get("total_desconto") or 0) for l in linhas)
        total_liquido = sum(float(l.get("total_liquido") or 0) for l in linhas)
        total_recebido = sum(float(l.get("total_liquido") or 0) for l in pagamentos_dia)
        total_lucro = sum(float(l.get("lucro_total") or 0) for l in linhas)
        qtd_vendas = sum(int(l.get("qtd_vendas") or 0) for l in linhas)
        cards = [
            ("Vendas entregues", str(qtd_vendas), COR["azul"]),
            ("Valor bruto", self._fmt(total_bruto), COR["cinza"]),
            ("Descontos", self._fmt(total_desc), COR["amarelo"]),
            ("Líquido vendido", self._fmt(total_liquido), COR["dourado"]),
            ("Recebido no dia", self._fmt(total_recebido), COR["verde"]),
            ("Fiado em aberto", self._fmt(total_fiado), COR["laranja"]),
            ("Lucro estimado", self._fmt(total_lucro), COR["verde"] if total_lucro >= 0 else COR["vermelho"]),
        ]
        for indice, (titulo, valor, cor) in enumerate(cards):
            card = ctk.CTkFrame(
                self.frame_cards, fg_color=COR["card"], corner_radius=RAIO_CARD,
                border_width=1, border_color=COR["borda"],
            )
            card.grid(row=indice // 4, column=indice % 4, padx=3, pady=3, sticky="nsew")
            ctk.CTkLabel(
                card, text=titulo, font=ctk.CTkFont(size=10), text_color=COR["cinza"],
            ).pack(anchor="w", padx=12, pady=(9, 2))
            ctk.CTkLabel(
                card, text=valor, font=ctk.CTkFont(size=16, weight="bold"), text_color=cor,
            ).pack(anchor="w", padx=12, pady=(0, 10))

        self._desenhar_grafico(pagamentos_dia)
        ctk.CTkLabel(
            self.container, text="Detalhamento dos recebimentos",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=COR["texto"], anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))
        if not pagamentos_dia:
            self._mensagem("Nenhum pagamento foi recebido durante este dia.")
        else:
            for pagamento in pagamentos_dia:
                linha = ctk.CTkFrame(
                    self.container, fg_color=COR["superficie"], corner_radius=RAIO_BOTAO,
                )
                linha.pack(fill="x", padx=8, pady=3)
                ctk.CTkLabel(
                    linha, text=pagamento.get("forma_pagamento") or "Não informado",
                    font=ctk.CTkFont(size=11, weight="bold"), text_color=COR["texto"],
                ).pack(side="left", padx=10, pady=8)
                ctk.CTkLabel(
                    linha, text=f"{int(pagamento.get('qtd_vendas') or 0)} venda(s)",
                    font=ctk.CTkFont(size=10), text_color=COR["cinza"],
                ).pack(side="left", padx=8)
                ctk.CTkLabel(
                    linha, text=self._fmt(float(pagamento.get("total_liquido") or 0)),
                    font=ctk.CTkFont(size=12, weight="bold"), text_color=COR["verde"],
                ).pack(side="right", padx=12, pady=8)