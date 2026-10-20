import math

import customtkinter as ctk
from tkinter import messagebox
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO
from ui.components.widgets import habilitar_foco_teclado, focar_controle
from ui.components.page_header import construir_cabecalho



class PaginaDias(ctk.CTkFrame):
    TAMANHO_PAGINA = 25

    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        construir_cabecalho(
            self,
            "Dias de operação",
            "Consulte os turnos anteriores e seus fechamentos. Os valores registrados no fechamento preservam a fotografia daquele momento.",
        )
        self.pagina = 0
        self.lbl_resultados = ctk.CTkLabel(
            self, text="", text_color=COR["cinza"], font=ctk.CTkFont(size=11), anchor="w",
        )
        self.lbl_resultados.pack(fill="x", padx=22, pady=(0, 4))

        self.controles_paginacao = ctk.CTkFrame(self, fg_color="transparent")
        self.controles_paginacao.pack(side="bottom", fill="x", padx=20, pady=(4, 12))
        self.btn_anterior = ctk.CTkButton(
            self.controles_paginacao, text="← Anterior", width=112,
            command=lambda: self._mudar_pagina(-1), corner_radius=RAIO_BOTAO,
            fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"], border_width=1, border_color=COR["borda"],
        )
        self.btn_anterior.pack(side="left")
        self.lbl_pagina = ctk.CTkLabel(self.controles_paginacao, text="Página 1 de 1", text_color=COR["cinza"])
        self.lbl_pagina.pack(side="left", expand=True)
        self.btn_proxima = ctk.CTkButton(
            self.controles_paginacao, text="Próxima →", width=112,
            command=lambda: self._mudar_pagina(1), corner_radius=RAIO_BOTAO,
            fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"], border_width=1, border_color=COR["borda"],
        )
        self.btn_proxima.pack(side="right")

        self.container = ctk.CTkScrollableFrame(self, fg_color=COR["fundo"])
        self.container.pack(fill="both", expand=True, padx=17, pady=(0, 4))
        self._carregar()

    def _mudar_pagina(self, delta: int):
        self.pagina = max(0, self.pagina + delta)
        self._carregar()

    def _carregar(self):
        for w in self.container.winfo_children():
            w.destroy()
        total = database.contar_dias_operacao()
        total_paginas = max(1, math.ceil(total / self.TAMANHO_PAGINA))
        self.pagina = min(self.pagina, total_paginas - 1)
        dias = database.listar_dias_operacao(
            limite=self.TAMANHO_PAGINA, offset=self.pagina * self.TAMANHO_PAGINA,
        )
        inicio = self.pagina * self.TAMANHO_PAGINA + 1 if total else 0
        fim = min((self.pagina + 1) * self.TAMANHO_PAGINA, total)
        self.lbl_resultados.configure(text=f"Exibindo {inicio}–{fim} de {total} dias de operação")
        self.lbl_pagina.configure(text=f"Página {self.pagina + 1} de {total_paginas}")
        self.btn_anterior.configure(state="normal" if self.pagina > 0 else "disabled")
        self.btn_proxima.configure(state="normal" if self.pagina + 1 < total_paginas else "disabled")
        if not dias:
            ctk.CTkLabel(
                self.container, text="Nenhum dia de operação registrado ainda.",
                text_color=COR["cinza"], font=ctk.CTkFont(size=12),
            ).pack(pady=40)
            return
        for original in dias:
            dia = dict(original)
            aberto = dia["status"] == "aberto"
            cor = COR["verde"] if aberto else COR["cinza"]
            frame = ctk.CTkFrame(
                self.container, fg_color=COR["card"], corner_radius=RAIO_CARD,
                border_width=1, border_color=COR["borda"],
            )
            frame.pack(fill="x", padx=3, pady=3)

            marcador = ctk.CTkFrame(frame, fg_color=cor, width=4, corner_radius=2)
            marcador.pack(side="left", fill="y", padx=(0, 12), pady=9)
            detalhes = ctk.CTkFrame(frame, fg_color="transparent")
            detalhes.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=10)
            ctk.CTkLabel(
                detalhes, text=f"Operação de {dia['data_abertura']}",
                font=ctk.CTkFont(size=13, weight="bold"), text_color=COR["texto"], anchor="w",
            ).pack(anchor="w")
            fim = f"Fechado às {dia['horario_fechamento']}" if not aberto else "Operação em andamento"
            ctk.CTkLabel(
                detalhes, text=f"Abertura: {dia['horario_abertura']}  ·  {fim}",
                font=ctk.CTkFont(size=10), text_color=COR["cinza"], anchor="w",
            ).pack(anchor="w", pady=(3, 0))

            ctk.CTkLabel(
                frame, text="ABERTO" if aberto else "FECHADO",
                font=ctk.CTkFont(size=10, weight="bold"), text_color=cor,
                fg_color=COR["superficie"], corner_radius=8,
            ).pack(side="right", padx=8, pady=10, ipadx=8, ipady=4)
            if not aberto:
                ctk.CTkButton(
                    frame, text="Ver fechamento", width=125, corner_radius=RAIO_BOTAO,
                    command=lambda d=dia["id"]: self._visualizar(d),
                    fg_color=COR["azul"], hover_color=COR["azul_h"],
                ).pack(side="right", padx=4, pady=10)

    def ao_mudar_tema(self):
        """Reconstrói as linhas com a paleta atual preservando a página."""
        self._carregar()

    def _visualizar(self, dia_id):
        info, linhas = database.obter_resumo_dia_operacao(dia_id)
        if not info:
            messagebox.showerror("Erro", "Dia não encontrado.")
            return
        janela = ctk.CTkToplevel(self)
        janela.title(f"Dia {info['data_abertura']}")
        janela.geometry("600x500")
        janela.configure(fg_color=COR["fundo"])
        janela.grab_set()
        ctk.CTkLabel(janela, text=f"Fechamento · {info['data_abertura']}", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COR["texto"]).pack(anchor="w", padx=20, pady=(20, 10))
        ctk.CTkLabel(janela, text=f"Abertura: {info['horario_abertura']} | Fechamento: {info.get('horario_fechamento', '---')}",
                     text_color=COR["cinza"]).pack()
        total_bruto = sum(float(l.get("total_bruto") or 0) for l in linhas)
        total_liquido = sum(float(l.get("total_liquido") or 0) for l in linhas)
        total_lucro = sum(float(l.get("lucro_total") or 0) for l in linhas)
        recebido_atual = sum(float(p.get("total_liquido") or 0) for p in database.obter_resumo_pagamentos_dia(dia_id))
        fiado_atual = database.obter_total_fiado_aberto()
        if info.get("total_vendido_fechamento") is not None:
            total_liquido = float(info.get("total_vendido_fechamento") or 0)
            total_lucro = float(info.get("lucro_estimado_fechamento") or 0)
            total_bruto = total_liquido + float(info.get("total_descontos_fechamento") or 0)
            recebido_atual = float(info.get("total_recebido_fechamento") or 0)
            fiado_atual = float(info.get("fiado_aberto_fechamento") or 0)
            qtd_vendas = int(info.get("quantidade_vendas_fechamento") or 0)
        else:
            # Dias anteriores à migração não têm fotografia de fechamento; valores são reconstruídos.
            qtd_vendas = sum(int(l.get("qtd_vendas") or 0) for l in linhas)
        ctk.CTkLabel(janela,
                     text=f"Vendas: {qtd_vendas} | Bruto: R${total_bruto:.2f} | "
                          f"Líquido vendido: R${total_liquido:.2f} | Recebido no dia: R${recebido_atual:.2f}\n"
                          f"Fiado em aberto no fechamento: R${fiado_atual:.2f} | Lucro estimado: R${total_lucro:.2f}",
                     font=ctk.CTkFont(size=13), text_color=COR["texto"]).pack(pady=10)
        vendas_frame = ctk.CTkScrollableFrame(janela, fg_color="transparent")
        vendas_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        vendas = database.listar_vendas(dia_operacao_id=dia_id)
        if not vendas:
            ctk.CTkLabel(vendas_frame, text="Nenhuma venda neste dia.", text_color=COR["cinza"]).pack(pady=20)
        else:
            for venda in vendas:
                f = ctk.CTkFrame(vendas_frame, fg_color=COR["card"], corner_radius=RAIO_BOTAO,
                                  border_width=1, border_color=COR["borda"])
                f.pack(fill="x", padx=3, pady=2)
                if venda.get("forma_pagamento") == "Fiado":
                    rotulo = "Fiado quitado" if venda["status"] == "finalizado" else "Fiado em aberto"
                    recibos = venda.get("pagamentos") or []
                    if recibos:
                        meios = ", ".join(f"{r['forma_pagamento']} R${float(r['valor']):.2f} ({r['data']})" for r in recibos)
                        rotulo += f" — recebimentos: {meios}"
                elif len(venda.get("pagamentos") or []) > 1:
                    rotulo = "Misto: " + ", ".join(f"{r['forma_pagamento']} R${float(r['valor']):.2f}" for r in venda["pagamentos"])
                else:
                    rotulo = venda.get("forma_pagamento") or "Não informado"
                ctk.CTkLabel(f, text=f"Venda {venda['id']} — {rotulo} — R${venda['total_liquido']:.2f}",
                             text_color=COR["texto"]).pack(side="left", padx=8, pady=4)
        btn_fechar = ctk.CTkButton(janela, text="Fechar janela", command=janela.destroy, corner_radius=RAIO_BOTAO,
                                   fg_color=COR["superficie"], hover_color=COR["hover"],
                                   text_color=COR["texto"], border_width=1, border_color=COR["borda"])
        btn_fechar.pack(pady=(0, 14))
        habilitar_foco_teclado(janela)
        janela.after_idle(lambda: focar_controle(btn_fechar))
