import math

import customtkinter as ctk
from tkinter import messagebox
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO

from ui.components.calendar import SeletorData
from ui.components.page_header import construir_cabecalho


class PaginaPedidos(ctk.CTkFrame):
    TAMANHO_PAGINA = 25

    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        construir_cabecalho(
            self,
            "Pedidos e fiado",
            "Acompanhe vendas entregues, pagamentos pendentes e recebimentos. Registre a quitação quando o cliente pagar.",
        )

        topo = ctk.CTkFrame(
            self, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        topo.pack(fill="x", padx=20, pady=(0, 8))

        self.pagina = 0
        ctk.CTkLabel(topo, text="Status", text_color=COR["cinza"],
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(12, 6), pady=10)
        self.filtro_status = ctk.CTkComboBox(
            topo, width=140, values=["Todos", "pendente", "finalizado"],
            command=lambda _: self._alterar_filtro(), fg_color=COR["input"],
            border_color=COR["borda"], button_color=COR["superficie"],
            dropdown_fg_color=COR["card"], dropdown_text_color=COR["texto"],
        )
        self.filtro_status.set("Todos")
        self.filtro_status.pack(side="left", padx=(0, 14), pady=8)

        ctk.CTkLabel(topo, text="Data", text_color=COR["cinza"],
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 6), pady=10)
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

    def _alterar_filtro(self):
        self.pagina = 0
        self._carregar()

    def _mudar_pagina(self, delta: int):
        self.pagina = max(0, self.pagina + delta)
        self._carregar()

    def _carregar(self):
        for w in self.container.winfo_children():
            w.destroy()
        status = self.filtro_status.get()
        if status == "Todos":
            status = None
        data = self.seletor_data.get_data_str()
        total = database.contar_vendas(status=status, data_inicio=data, data_fim=data)
        total_paginas = max(1, math.ceil(total / self.TAMANHO_PAGINA))
        self.pagina = min(self.pagina, total_paginas - 1)
        vendas = database.listar_vendas(
            status=status, data_inicio=data, data_fim=data,
            limite=self.TAMANHO_PAGINA, offset=self.pagina * self.TAMANHO_PAGINA,
        )
        inicio = self.pagina * self.TAMANHO_PAGINA + 1 if total else 0
        fim = min((self.pagina + 1) * self.TAMANHO_PAGINA, total)
        self.lbl_resultados.configure(text=f"Exibindo {inicio}–{fim} de {total} venda(s)")
        self.lbl_pagina.configure(text=f"Página {self.pagina + 1} de {total_paginas}")
        self.btn_anterior.configure(state="normal" if self.pagina > 0 else "disabled")
        self.btn_proxima.configure(state="normal" if self.pagina + 1 < total_paginas else "disabled")

        if not vendas:
            ctk.CTkLabel(self.container, text="Nenhuma venda encontrada para este filtro.",
                         text_color=COR["cinza"]).pack(pady=30)
            return

        for venda in vendas:
            cor = COR["verde"] if venda["status"] == "finalizado" else COR["amarelo"]
            frame = ctk.CTkFrame(self.container, fg_color=COR["card"], corner_radius=RAIO_CARD,
                                  border_width=1, border_color=COR["borda"])
            frame.pack(fill="x", padx=4, pady=4)
            header = ctk.CTkFrame(frame, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(header, text=f"Venda #{venda['id']}", font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=COR["texto"]).pack(side="left")
            ctk.CTkLabel(header, text=f" {'FIADO EM ABERTO' if venda['status']=='pendente' else venda['status'].upper()} ", font=ctk.CTkFont(size=10, weight="bold"),
                         fg_color=COR["superficie"], text_color=cor, corner_radius=8, padx=8, pady=3).pack(side="right")
            ctk.CTkLabel(header, text=venda["data"], font=ctk.CTkFont(size=10),
                         text_color=COR["cinza"]).pack(side="right", padx=10)
            info = ctk.CTkFrame(frame, fg_color="transparent")
            info.pack(fill="x", padx=10, pady=(0, 4))
            if venda.get("cliente_nome"):
                ctk.CTkLabel(info, text=f"Cliente: {venda['cliente_nome']}", text_color=COR["texto"]).pack(side="left", padx=(0, 15))
            ctk.CTkLabel(info, text=f"Pagamento: {venda['forma_pagamento'] or 'Não informado'}",
                         text_color=COR["texto"], font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 15))
            if venda["desconto_valor"] > 0:
                ctk.CTkLabel(info, text=f"🔻 Desc. geral: R$ {venda['desconto_valor']:.2f}",
                             text_color=COR["amarelo"]).pack(side="left", padx=(0, 15))
            ctk.CTkLabel(info, text=f"Total: R$ {venda['total_liquido']:.2f}",
                         font=ctk.CTkFont(size=14, weight="bold"), text_color=COR["dourado"]).pack(side="right")
            if venda.get("lucro_total", 0) != 0:
                cor_lucro = COR["verde"] if venda["lucro_total"] > 0 else COR["vermelho"]
                ctk.CTkLabel(info, text=f"Lucro: R$ {venda['lucro_total']:.2f}",
                             text_color=cor_lucro, font=ctk.CTkFont(weight="bold")).pack(side="right", padx=(0, 15))
            if venda.get("observacao"):
                ctk.CTkLabel(frame, text=f"Observação: {venda['observacao']}",
                             text_color=COR["cinza"], font=ctk.CTkFont(size=11, slant="italic"),
                             anchor="w").pack(fill="x", padx=10, pady=(0, 4))
            if venda["itens"]:
                itens_frame = ctk.CTkFrame(frame, fg_color=COR["fundo"], corner_radius=RAIO_BOTAO)
                itens_frame.pack(fill="x", padx=10, pady=(0, 8))
                for item in venda["itens"]:
                    desc = f"{item['nome_produto']}  ×  {item['quantidade']}  ·  R$ {item['preco_unitario']:.2f}/un."
                    if item.get("desconto_percentual", 0) > 0:
                        desc += f"  ·  desconto {item['desconto_percentual']:.0f}%"
                    desc += f" = R$ {item['subtotal']:.2f}"
                    if item.get("lucro_item", 0) != 0:
                        desc += f" | Lucro: R$ {item['lucro_item']:.2f}"
                    ctk.CTkLabel(itens_frame, text=desc, text_color=COR["cinza"],
                                 font=ctk.CTkFont(size=11), anchor="w").pack(anchor="w", padx=8, pady=2)
            if venda["status"] == "pendente":
                ctk.CTkButton(frame, text="Registrar recebimento", corner_radius=RAIO_BOTAO,
                              command=lambda v=venda["id"]: self._concluir(v),
                              fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(anchor="e", padx=10, pady=(0, 8))

    def _concluir(self, venda_id):
        try:
            vendas = database.listar_vendas(status="pendente", venda_id=venda_id)
            venda = vendas[0] if vendas else None
            if not venda:
                messagebox.showerror("Fiado não encontrado", "Atualize a lista e tente novamente.")
                self._carregar()
                return
            from ui.components.payment_dialog import coletar_pagamentos
            pagamentos = coletar_pagamentos(self, venda["total_liquido"], "Dinheiro", forcar_dialogo=True)
            if pagamentos is None:
                return
            database.atualizar_status_venda(venda_id, "finalizado", pagamentos)
            messagebox.showinfo("Fiado quitado", f"Venda {venda_id} foi quitada e o recebimento foi registrado.")
            self._carregar()
            self.app.atualizar_todas_abas()
        except Exception as exc:
            messagebox.showerror("Erro ao registrar pagamento", str(exc))
