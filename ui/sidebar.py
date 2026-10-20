"""Navegação principal do BARNS, com estados visuais e foco por teclado."""
import logging

import customtkinter as ctk
from tkinter import messagebox

import database
from ui.theme import COR, RAIO_BOTAO, modo_noturno_ativo
from ui.components.widgets import StatusDot, habilitar_foco_teclado
from ui.components.sidebar_button import SidebarButton

log = logging.getLogger(__name__)


class BarraLateral(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, width=178, fg_color=COR["card"], corner_radius=0, border_width=1, border_color=COR["borda"])
        self.app = app
        self._nav_buttons = []
        self._botoes_por_nome = {}
        self.pack(side="left", fill="y")
        self.pack_propagate(False)

        marca = ctk.CTkFrame(self, fg_color="transparent")
        marca.pack(fill="x", padx=16, pady=(20, 5))
        ctk.CTkLabel(
            marca, text="B", width=34, height=34, corner_radius=10,
            fg_color=COR["vinho"], text_color=COR["texto_sobre_marca"],
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        textos_marca = ctk.CTkFrame(marca, fg_color="transparent")
        textos_marca.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(textos_marca, text="BARNS", font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                     text_color=COR["texto"]).pack(anchor="w")
        ctk.CTkLabel(textos_marca, text="ADEGA · PDV", font=ctk.CTkFont(size=9, weight="normal"),
                     text_color=COR["cinza"]).pack(anchor="w", pady=(1, 0))
        ctk.CTkFrame(self, height=1, fg_color=COR["borda"]).pack(fill="x", padx=14, pady=12)

        grupos = [
            [("vendas", "Vendas"), ("estoque", "Estoque"), ("banco", "Banco")],
            [("historico", "Histórico"), ("pedidos", "Pedidos"),
             ("resumo", "Resumo"), ("dias", "Dias")],
        ]
        for indice_grupo, grupo in enumerate(grupos):
            for icon_id, label in grupo:
                botao = SidebarButton(
                    self, icon_id, label,
                    command=lambda n=label: self.app.mostrar_pagina(n),
                )
                botao.pack(pady=3, padx=10, fill="x")
                self._nav_buttons.append(botao)
                self._botoes_por_nome[label] = botao
            if indice_grupo == 0:
                ctk.CTkFrame(self, height=1, fg_color=COR["borda"]).pack(fill="x", padx=16, pady=10)

        ctk.CTkFrame(self, height=1, fg_color=COR["borda"]).pack(fill="x", padx=14, pady=10)
        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(side="bottom", fill="x", pady=(4, 12))
        self.dot_status = StatusDot(rodape, COR["vermelho"], tamanho=12)
        self.dot_status.pack(pady=(0, 5))
        self.btn_dia = ctk.CTkButton(
            rodape, text="Iniciar", width=140, height=32,
            font=ctk.CTkFont(size=11, weight="bold"), corner_radius=RAIO_BOTAO,
            fg_color=COR["verde"], hover_color=COR["verde_h"],
            command=self._iniciar_dia,
        )
        self.btn_dia.pack(anchor="center", padx=12, fill="x")

        # O controle fica acima do estado do dia e permanece disponível em todas as páginas.
        aparencia = ctk.CTkFrame(self, fg_color="transparent")
        aparencia.pack(side="bottom", fill="x", padx=12, pady=(4, 8))
        self.var_modo_noturno = ctk.BooleanVar(master=self, value=modo_noturno_ativo())
        self.chk_modo_noturno = ctk.CTkCheckBox(
            aparencia,
            text="Modo noturno",
            variable=self.var_modo_noturno,
            command=self._alternar_modo_noturno,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=5,
            border_width=1,
            fg_color=COR["azul"],
            hover_color=COR["azul_h"],
            border_color=COR["borda_azul"],
            checkmark_color=COR["texto_sobre_marca"],
            text_color=COR["texto"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self.chk_modo_noturno.pack(anchor="w", padx=2, pady=5)
        self._atualizar_status_dia()
        habilitar_foco_teclado(self)

    def _alternar_modo_noturno(self):
        self.app.alternar_tema(bool(self.var_modo_noturno.get()))

    def _atualizar_status_dia(self):
        dia = database.obter_dia_aberto()
        if dia:
            self.dot_status.set_cor(COR["verde"])
            self.btn_dia.configure(text="Fechar", fg_color=COR["vermelho"],
                                   hover_color=COR["vermelho_h"], command=self._fechar_dia)
        else:
            self.dot_status.set_cor(COR["vermelho"])
            self.btn_dia.configure(text="Iniciar", fg_color=COR["verde"],
                                   hover_color=COR["verde_h"], command=self._iniciar_dia)
        habilitar_foco_teclado(self)

    def _iniciar_dia(self):
        if database.obter_dia_aberto():
            messagebox.showinfo("Aviso", "Já existe um dia aberto.", parent=self)
            return
        if messagebox.askyesno("Iniciar dia", "Deseja iniciar um novo dia de operação agora?", parent=self):
            try:
                dia_id, abriu = database.abrir_dia()
                if not abriu or dia_id is None:
                    messagebox.showwarning("Dia já aberto", "Outro fluxo abriu o dia de operação. Atualize o status e tente novamente.", parent=self)
                    self._atualizar_status_dia()
                    return
                self._atualizar_status_dia()
                self.app.atualizar_todas_abas()
                messagebox.showinfo("Dia iniciado", "Dia de operação iniciado com sucesso.", parent=self)
            except Exception as exc:
                log.exception("Falha ao iniciar dia de operação")
                messagebox.showerror("Não foi possível iniciar o dia", str(exc), parent=self)

    def _fechar_dia(self):
        dia = database.obter_dia_aberto()
        if not dia:
            messagebox.showinfo("Aviso", "Nenhum dia aberto.", parent=self)
            return
        try:
            info, linhas = database.obter_resumo_dia_operacao(dia["id"])
            vendido = sum(float(l.get("total_liquido") or 0) for l in linhas)
            recebido = sum(float(p.get("total_liquido") or 0) for p in database.obter_resumo_pagamentos_dia(dia["id"]))
            fiado = database.obter_total_fiado_aberto()
            confirmar = messagebox.askyesno(
                "Fechar dia",
                f"Fechar dia {info['data_abertura']}?\n\n"
                f"Vendido: R$ {vendido:.2f}\nRecebido: R$ {recebido:.2f}\nFiado em aberto: R$ {fiado:.2f}",
                parent=self,
            )
            if not confirmar:
                return
            database.fechar_dia(dia["id"])
            self._atualizar_status_dia()
            self.app.atualizar_todas_abas()
            messagebox.showinfo("Dia fechado", "Dia de operação fechado com sucesso.", parent=self)
        except Exception as exc:
            log.exception("Falha ao fechar dia de operação")
            messagebox.showerror("Não foi possível fechar o dia", str(exc), parent=self)
