import customtkinter as ctk
from tkinter import messagebox
from typing import List, Dict
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO

from ui.components.widgets import AutocompleteEntry, habilitar_foco_teclado, remover_acentos


class PaginaVendas(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        self.carrinho: List[Dict] = []
        self._cache: List[Dict] = []
        self._desconto_valido = True
        self._construir()
        self._recarregar_produtos()

    def _construir(self):
        painel_esq = ctk.CTkFrame(self, fg_color=COR["card"], corner_radius=RAIO_CARD,
                                   border_width=1, border_color=COR["borda"])
        painel_esq.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)

        ctk.CTkLabel(painel_esq, text="Ponto de venda",
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     text_color=COR["texto"]).pack(anchor="w", padx=18, pady=(18, 2))
        ctk.CTkLabel(painel_esq, text="Digite o produto e pressione Enter para adicionar. Use ↑/↓ para escolher outra sugestão.",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COR["cinza"]).pack(anchor="w", padx=18, pady=(0, 13))

        self.autocomplete = AutocompleteEntry(
            painel_esq, items_callback=self._obter_sugestoes, on_enter_callback=self._adicionar_rapido
        )
        self.autocomplete.pack(fill="x", padx=18, pady=(0, 10))

        ctrl_frame = ctk.CTkFrame(painel_esq, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=18, pady=5)

        ctk.CTkLabel(ctrl_frame, text="Qtd:", text_color=COR["texto"]).pack(side="left", padx=(0, 5))
        self.campo_qtd = ctk.CTkEntry(ctrl_frame, width=70, fg_color=COR["input"],
                                       text_color=COR["texto"], border_color=COR["borda_azul"])
        self.campo_qtd.insert(0, "1")
        self.campo_qtd.pack(side="left", padx=(0, 15))
        self.campo_qtd.bind("<Return>", lambda e: self._adicionar())

        ctk.CTkLabel(ctrl_frame, text="Cód.Barras:", text_color=COR["texto"]).pack(side="left", padx=(0, 5))
        self.campo_codigo = ctk.CTkEntry(ctrl_frame, width=160, fg_color=COR["input"],
                                          text_color=COR["texto"], border_color=COR["borda_azul"])
        self.campo_codigo.pack(side="left")
        self.campo_codigo.bind("<Return>", self._processar_codigo_barras)

        ctk.CTkButton(ctrl_frame, text="Adicionar", width=80, command=self._adicionar,
                      corner_radius=RAIO_BOTAO,
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(side="right", padx=(10, 0))
        ctk.CTkButton(ctrl_frame, text="Dose", width=70, command=self._vender_dose,
                      corner_radius=RAIO_BOTAO,
                      fg_color=COR["laranja"], hover_color=COR["amarelo"]).pack(side="right")

        info_frame = ctk.CTkFrame(painel_esq, fg_color="transparent")
        info_frame.pack(fill="x", padx=18, pady=10)

        ctk.CTkLabel(info_frame, text="Desc. Geral (R$ ou %):",
                     text_color=COR["texto"]).pack(side="left", padx=(0, 5))
        self.campo_desconto = ctk.CTkEntry(info_frame, width=100, placeholder_text="0",
                                            fg_color=COR["input"], text_color=COR["texto"],
                                            border_color=COR["amarelo"])
        self.campo_desconto.insert(0, "0")
        self.campo_desconto.pack(side="left", padx=(0, 15))
        # O desconto geral altera o total, não os controles de cada linha.
        # Atualizar somente os totais evita destruir/recriar widgets a cada tecla.
        self.campo_desconto.bind("<KeyRelease>", self._atualizar_totais_exibidos)

        ctk.CTkLabel(info_frame, text="Pagamento:", text_color=COR["texto"]).pack(side="left", padx=(0, 5))
        self.forma_pagamento = ctk.CTkComboBox(info_frame, width=140,
                                                values=["Dinheiro", "Cartão", "Pix", "Misto"],
                                                state="readonly", fg_color=COR["input"],
                                                border_color=COR["borda_azul"])
        self.forma_pagamento.set("Dinheiro")
        self.forma_pagamento.pack(side="left")

        # Campos de identificação agrupados para uma leitura mais clara no balcão.
        detalhes_card = ctk.CTkFrame(
            painel_esq, fg_color=COR["superficie"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        detalhes_card.pack(fill="x", padx=18, pady=(4, 14))

        detalhes_header = ctk.CTkFrame(detalhes_card, fg_color="transparent")
        detalhes_header.pack(fill="x", padx=13, pady=(11, 7))
        ctk.CTkLabel(
            detalhes_header, text="Detalhes da venda",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COR["texto"],
        ).pack(side="left")
        ctk.CTkLabel(
            detalhes_header, text="Dados adicionais",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COR["cinza"],
        ).pack(side="right")

        cliente_header = ctk.CTkFrame(detalhes_card, fg_color="transparent")
        cliente_header.pack(fill="x", padx=13, pady=(2, 4))
        ctk.CTkLabel(
            cliente_header, text="Cliente",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COR["texto"],
        ).pack(side="left")
        ctk.CTkLabel(
            cliente_header, text="Obrigatório para fiado", corner_radius=6,
            fg_color=COR["hover"], text_color=COR["azul"],
            font=ctk.CTkFont(family="Segoe UI", size=9), padx=8, pady=3,
        ).pack(side="right")
        self.campo_cliente = ctk.CTkEntry(
            detalhes_card, placeholder_text="Nome do cliente",
            height=36, fg_color=COR["input"], text_color=COR["texto"],
            border_color=COR["borda_azul"], corner_radius=RAIO_BOTAO,
        )
        self.campo_cliente.pack(fill="x", padx=13, pady=(0, 9))

        obs_header = ctk.CTkFrame(detalhes_card, fg_color="transparent")
        obs_header.pack(fill="x", padx=13, pady=(0, 4))
        ctk.CTkLabel(
            obs_header, text="Observações",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COR["texto"],
        ).pack(side="left")
        ctk.CTkLabel(
            obs_header, text="Opcional",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=COR["cinza"],
        ).pack(side="right")
        self.campo_obs = ctk.CTkEntry(
            detalhes_card,
            placeholder_text="Ex.: entrega, encomenda ou referência interna",
            height=36, fg_color=COR["input"], text_color=COR["texto"],
            border_color=COR["borda"], corner_radius=RAIO_BOTAO,
        )
        self.campo_obs.pack(fill="x", padx=13, pady=(0, 13))

        painel_dir = ctk.CTkFrame(self, fg_color=COR["card"], corner_radius=RAIO_CARD,
                                   border_width=1, border_color=COR["borda"])
        painel_dir.pack(side="right", fill="both", expand=True, padx=(6, 12), pady=12)

        titulo_carrinho = ctk.CTkFrame(painel_dir, fg_color="transparent")
        titulo_carrinho.pack(fill="x", padx=16, pady=(19, 10))
        ctk.CTkLabel(titulo_carrinho, text="Carrinho",
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color=COR["texto"]).pack(side="left")
        ctk.CTkLabel(titulo_carrinho, text="Enter adiciona · F12 finaliza",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=COR["cinza"]).pack(side="right")

        self.frame_carrinho = ctk.CTkScrollableFrame(painel_dir, fg_color=COR["fundo"])
        self.frame_carrinho.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        rodape = ctk.CTkFrame(painel_dir, fg_color="transparent")
        rodape.pack(fill="x", padx=14, pady=12)

        self.lbl_total = ctk.CTkLabel(rodape, text="TOTAL: R$ 0,00",
                                       font=ctk.CTkFont(size=22, weight="bold"),
                                       text_color=COR["dourado"])
        self.lbl_total.pack(pady=(5, 2))
        self.lbl_itens = ctk.CTkLabel(rodape, text="0 itens", text_color=COR["cinza"])
        self.lbl_itens.pack()

        botoes_frame = ctk.CTkFrame(rodape, fg_color="transparent")
        botoes_frame.pack(fill="x", pady=(12, 4))

        ctk.CTkButton(botoes_frame, text="Cancelar (Esc)", width=130, command=self._cancelar,
                      corner_radius=RAIO_BOTAO,
                      fg_color=COR["vermelho"], hover_color=COR["vermelho_h"]).pack(side="left")
        ctk.CTkButton(botoes_frame, text="Fiado (F2)", width=130,
                      command=lambda: self._finalizar("pendente"),
                      corner_radius=RAIO_BOTAO,
                      fg_color=COR["amarelo"], text_color=COR["texto_sobre_alerta"]).pack(side="right", padx=(5, 0))
        ctk.CTkButton(botoes_frame, text="Finalizar (F12)", width=130,
                      command=lambda: self._finalizar("finalizado"),
                      corner_radius=RAIO_BOTAO,
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(side="right", padx=(5, 0))

        self._renderizar_carrinho()
        # A página pode ser construída antes de ser exibida; foco é aplicado
        # depois que o Tk concluir o primeiro layout.
        self.after_idle(self.campo_codigo.focus_set)

    def _obter_sugestoes(self, termo):
        self._cache = database.buscar_produtos(termo, limite=self.autocomplete.max_items)
        return [f"{p['nome']} — R$ {p['preco']:.2f}" for p in self._cache]

    def _adicionar_rapido(self):
        nome = self.autocomplete.get_selected_product_name()
        if not nome:
            return
        produto = next((p for p in self._cache if p["nome"] == nome), None)
        if not produto:
            resultados = database.buscar_produtos(nome, limite=25)
            produto = next((p for p in resultados if p["nome"] == nome), None)
            if not produto:
                return
        self._adicionar_produto(produto)

    def _adicionar_produto(self, produto):
        try:
            texto_qtd = self.campo_qtd.get().strip() or "1"
            qtd = int(texto_qtd)
        except (ValueError, OverflowError):
            messagebox.showwarning("Quantidade inválida", "Informe um número inteiro positivo para a quantidade.")
            self.campo_qtd.focus_set()
            return False
        if qtd <= 0:
            messagebox.showwarning("Quantidade inválida", "A quantidade precisa ser maior que zero.")
            self.campo_qtd.focus_set()
            return False
        # Contabiliza o que já está no carrinho para não ultrapassar o estoque ao adicionar o mesmo item duas vezes.
        quantidade_no_carrinho = sum(int(i["qtd"]) for i in self.carrinho
                                     if i["id"] == produto["id"] and i.get("tipo") != "dose")
        estoque_atual = int(produto.get("quantidade", 0))
        if quantidade_no_carrinho + qtd > estoque_atual:
            messagebox.showwarning("Estoque insuficiente", f"Disponível: {estoque_atual} un.; no carrinho: {quantidade_no_carrinho} un.")
            return False
        existente = next((i for i in self.carrinho if i["id"] == produto["id"] and i.get("tipo") != "dose"), None)
        if existente:
            existente["qtd"] += qtd
        else:
            self.carrinho.append({"id": produto["id"], "nome": produto["nome"],
                                  "preco": produto["preco"], "qtd": qtd, "desconto_valor": 0.0})
        self.campo_qtd.delete(0, "end")
        self.campo_qtd.insert(0, "1")
        self.autocomplete.set("")
        self.autocomplete.entry.focus()
        self._renderizar_carrinho()
        return True

    def _processar_codigo_barras(self, event=None):
        codigo = self.campo_codigo.get().strip()
        if not codigo:
            return
        produto = database.buscar_produto_por_codigo_barras(codigo)
        if not produto:
            messagebox.showerror("Erro", "Produto não encontrado.")
            self.campo_codigo.delete(0, "end")
            return
        if self._adicionar_produto(produto):
            self.campo_codigo.delete(0, "end")

    def _adicionar(self):
        nome = self.autocomplete.get_selected_product_name()
        if nome:
            produto = next((p for p in self._cache if p["nome"] == nome), None)
            if produto:
                self._adicionar_produto(produto)

    def _vender_dose(self):
        todas = database.buscar_produtos("")
        garrafas = [p for p in todas if p.get("is_garrafa")]
        if not garrafas:
            messagebox.showinfo("Aviso", "Nenhum produto cadastrado como garrafa (marque 'É garrafa' ao cadastrar).")
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Vender Dose")
        janela.geometry("540x340")
        janela.configure(fg_color=COR["card"])
        janela.grab_set()

        ctk.CTkLabel(janela, text="Selecione a garrafa:", text_color=COR["texto"]).pack(pady=(15, 5))
        doses_por_produto = database.obter_doses_disponiveis_por_produto()

        def sugestoes_dose(termo):
            filtradas = []
            termo_limpo = remover_acentos(termo.lower())
            for g in garrafas:
                doses_disp = doses_por_produto.get(g["id"], 0.0)
                texto = f"{g['nome']} — R$ {g['preco']:.2f} (dose R$ {g['preco_dose']:.2f}) [disp: {doses_disp:.1f}]"
                if termo_limpo in remover_acentos(texto.lower()):
                    filtradas.append(texto)
            return filtradas

        # Widgets locais (closure) — evita conflito entre diálogos consecutivos
        ac_dose = AutocompleteEntry(janela, items_callback=sugestoes_dose, max_items=6)
        ac_dose.pack(fill="x", padx=20, pady=5)

        frame_qtd = ctk.CTkFrame(janela, fg_color="transparent")
        frame_qtd.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_qtd, text="Qtd. doses:", text_color=COR["texto"]).pack(side="left", padx=(0, 5))
        entry_dose_qtd = ctk.CTkEntry(frame_qtd, width=80, fg_color=COR["input"],
                                       text_color=COR["texto"], border_color=COR["borda_azul"])
        entry_dose_qtd.insert(0, "1")
        entry_dose_qtd.pack(side="left")

        def confirmar():
            nome_sel = ac_dose.get_selected_product_name()
            if not nome_sel:
                messagebox.showwarning("Aviso", "Selecione uma garrafa.")
                return
            produto = next((p for p in garrafas if p["nome"] == nome_sel), None)
            if not produto:
                messagebox.showerror("Erro", "Garrafa não encontrada.")
                return
            try:
                qtd = int(entry_dose_qtd.get().strip())
            except ValueError:
                messagebox.showerror("Erro", "Quantidade inválida.")
                return
            if qtd <= 0:
                messagebox.showerror("Erro", "Quantidade deve ser positiva.")
                return

            # A disponibilidade exata é validada para o carrinho inteiro ao finalizar.
            # A confirmação de abertura ocorre apenas nesse momento, evitando prompts duplicados.
            self.carrinho.append({
                "id": produto["id"], "nome": f"Dose: {produto['nome']}",
                "preco": produto["preco_dose"], "qtd": qtd,
                "desconto_valor": 0.0, "tipo": "dose"
            })
            self._renderizar_carrinho()
            janela.destroy()

        ctk.CTkButton(janela, text="Adicionar ao carrinho", command=confirmar,
                      corner_radius=RAIO_BOTAO,
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(pady=20)
        habilitar_foco_teclado(janela)
        janela.after_idle(ac_dose.entry.focus_set)

    def _ajustar_qtd(self, idx, delta):
        self.carrinho[idx]["qtd"] += delta
        if self.carrinho[idx]["qtd"] <= 0:
            self.carrinho.pop(idx)
        self._renderizar_carrinho()

    def _ajustar_desconto_item(self, idx, valor_str):
        if not (0 <= idx < len(self.carrinho)):
            return
        bruto = max(0.0, float(self.carrinho[idx]["preco"]) * int(self.carrinho[idx]["qtd"]))
        texto = (valor_str or "0").strip().replace(",", ".")
        try:
            if texto.endswith("%"):
                percentual = float(texto[:-1])
                if not 0 <= percentual <= 100:
                    raise ValueError
                desconto = round(bruto * percentual / 100.0, 2)
            else:
                desconto = float(texto or "0")
                if not 0 <= desconto <= bruto:
                    raise ValueError
            self.carrinho[idx]["desconto_valor"] = round(desconto, 2)
        except (ValueError, OverflowError):
            messagebox.showerror("Desconto inválido", "Informe um valor entre R$ 0,00 e o subtotal do item, ou um percentual entre 0% e 100%.")
        self._renderizar_carrinho()

    def _remover_item(self, idx):
        self.carrinho.pop(idx)
        self._renderizar_carrinho()

    def _calcular_totais(self):
        total_bruto = round(sum(float(i["preco"]) * int(i["qtd"]) for i in self.carrinho), 2)
        total_desc_itens = round(sum(float(i.get("desconto_valor", 0)) for i in self.carrinho), 2)
        base = max(0.0, total_bruto - total_desc_itens)
        try:
            texto = self.campo_desconto.get().strip().replace(",", ".")
            if texto.endswith("%"):
                pct = float(texto[:-1])
                if not 0 <= pct <= 100: raise ValueError
                desc_geral = round(base * pct / 100.0, 2)
            else:
                desc_geral = float(texto or "0")
                if not 0 <= desc_geral <= base: raise ValueError
            self._desconto_valido = True
        except (ValueError, OverflowError):
            desc_geral = 0.0
            self._desconto_valido = False
        total_final = round(max(0.0, base - desc_geral), 2)
        return total_bruto, total_desc_itens, desc_geral, total_final

    def _atualizar_totais_exibidos(self, _event=None):
        _, _, _, total_final = self._calcular_totais()
        n_itens = sum(int(i["qtd"]) for i in self.carrinho)
        if self._desconto_valido:
            self.lbl_total.configure(text=f"TOTAL: R$ {total_final:.2f}", text_color=COR["dourado"])
        else:
            self.lbl_total.configure(text="DESCONTO INVÁLIDO", text_color=COR["vermelho"])
        self.lbl_itens.configure(text=f"{n_itens} itens" if n_itens != 1 else "1 item")
        return None

    def _renderizar_carrinho(self):
        for w in self.frame_carrinho.winfo_children():
            w.destroy()
        if not self.carrinho:
            # Explicitamente transparente: sem fg_color, o CTkLabel pode usar o
            # fundo padrão do tema e criar uma faixa clara dentro do carrinho escuro.
            ctk.CTkLabel(
                self.frame_carrinho,
                text="Carrinho vazio",
                fg_color="transparent",
                # ScrollableFrame utiliza um Frame Tk interno; explicitar o
                # bg_color evita herdar o fundo claro padrão do tema CTkLabel.
                bg_color=COR["fundo"],
                text_color=COR["cinza"],
                anchor="center",
            ).pack(fill="x", pady=30)
            self.lbl_total.configure(text="TOTAL: R$ 0,00")
            self.lbl_itens.configure(text="0 itens")
            return

        ids_doses = {int(item["id"]) for item in self.carrinho if item.get("tipo") == "dose"}
        doses_por_produto = database.obter_doses_disponiveis_por_produto() if ids_doses else {}
        for idx, item in enumerate(self.carrinho):
            frame_item = ctk.CTkFrame(self.frame_carrinho, fg_color=COR["input"],
                                       corner_radius=RAIO_BOTAO, border_width=1, border_color=COR["borda"])
            frame_item.pack(fill="x", padx=3, pady=3)

            topo = ctk.CTkFrame(frame_item, fg_color="transparent")
            topo.pack(fill="x", padx=8, pady=(6, 2))

            extra = ""
            if item.get("tipo") == "dose":
                doses_disp = doses_por_produto.get(int(item["id"]), 0.0)
                extra = f" (disp: {doses_disp:.1f})"
            ctk.CTkLabel(topo, text=item["nome"] + extra,
                         font=ctk.CTkFont(size=12, weight="bold"), text_color=COR["texto"]).pack(side="left")

            ctrl = ctk.CTkFrame(frame_item, fg_color="transparent")
            ctrl.pack(fill="x", padx=8, pady=(2, 6))

            ctk.CTkButton(ctrl, text="-", width=30, height=26, command=lambda i=idx: self._ajustar_qtd(i, -1),
                          corner_radius=RAIO_BOTAO,
                          fg_color=COR["vermelho"], hover_color=COR["vermelho_h"]).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(ctrl, text=str(item["qtd"]), width=30, text_color=COR["texto"]).pack(side="left")
            ctk.CTkButton(ctrl, text="+", width=30, height=26, command=lambda i=idx: self._ajustar_qtd(i, 1),
                          corner_radius=RAIO_BOTAO,
                          fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(side="left", padx=(5, 15))

            sub_bruto = item["preco"] * item["qtd"]
            ctk.CTkLabel(ctrl, text=f"R$ {item['preco']:.2f} un.", text_color=COR["cinza"]).pack(side="left", padx=(0, 10))
            ctk.CTkLabel(ctrl, text="Desc:", text_color=COR["cinza"]).pack(side="left", padx=(0, 3))

            desc_entry = ctk.CTkEntry(ctrl, width=80, height=24, fg_color=COR["card"],
                                       text_color=COR["texto"], border_color=COR["amarelo"])
            desc_valor = item.get("desconto_valor", 0)
            desc_entry.insert(0, f"{desc_valor:.2f}" if desc_valor > 0 else "0")
            desc_entry.pack(side="left", padx=(0, 10))
            desc_entry.bind("<FocusOut>", lambda e, i=idx: self._ajustar_desconto_item(i, e.widget.get()))
            desc_entry.bind("<Return>", lambda e, i=idx: self._ajustar_desconto_item(i, e.widget.get()))

            subtotal = sub_bruto - desc_valor
            ctk.CTkLabel(ctrl, text=f"= R$ {subtotal:.2f}", font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=COR["dourado"]).pack(side="left", padx=(0, 15))
            ctk.CTkButton(ctrl, text="X", width=30, height=26, command=lambda i=idx: self._remover_item(i),
                          corner_radius=RAIO_BOTAO,
                          fg_color=COR["vermelho"], hover_color=COR["vermelho_h"]).pack(side="right")

        self._atualizar_totais_exibidos()
        # Os botões de quantidade são recriados ao mudar o carrinho; reaplicar
        # o suporte a teclado faz os novos controles participarem do Tab.
        habilitar_foco_teclado(self.frame_carrinho)

    def _finalizar(self, status):
        if not self.carrinho:
            messagebox.showwarning("Venda vazia", "Adicione ao menos um item antes de finalizar.")
            return
        if status not in ("pendente", "finalizado"):
            messagebox.showerror("Status inválido", "Esse status de venda não é permitido.")
            return
        total_bruto, total_desc_itens, desc_geral, total_final = self._calcular_totais()
        if not self._desconto_valido:
            messagebox.showerror("Desconto inválido", "Corrija o desconto geral. Ele deve estar entre zero e o total após descontos por item; percentuais devem ficar entre 0% e 100%.")
            return
        base = max(0.0, total_bruto - total_desc_itens)
        pct_geral = (desc_geral / base * 100) if base > 0 else 0.0
        itens_para_venda = []
        for item in self.carrinho:
            bruto = float(item["preco"]) * int(item["qtd"])
            desconto_valor = float(item.get("desconto_valor", 0))
            pct_item = (desconto_valor / bruto * 100) if bruto > 0 else 0.0
            itens_para_venda.append({
                "produto_id": item["id"], "nome": item["nome"], "preco": item["preco"],
                "quantidade": item["qtd"], "desconto_percentual": pct_item,
                "tipo": item.get("tipo", "unidade"),
            })

        dia = database.obter_dia_aberto()
        dia_id = dia["id"] if dia else None
        if dia_id is None:
            messagebox.showerror("Dia não aberto", "Inicie o dia de operação antes de registrar uma venda.")
            return

        cliente = self.campo_cliente.get().strip()
        if status == "pendente" and not cliente:
            messagebox.showwarning("Cliente obrigatório", "Informe o nome do cliente para registrar um fiado.")
            self.campo_cliente.focus_set()
            return

        try:
            preflight = database.prever_abertura_garrafas(itens_para_venda)
            a_abrir = [p for p in preflight if p["garrafas_necessarias"] > 0]
            sem_estoque = [p for p in a_abrir if not p["suficiente"]]
            if sem_estoque:
                detalhes = "\n".join(f"{p['nome']}: precisa abrir {p['garrafas_necessarias']}, disponíveis {p['garrafas_disponiveis']}" for p in sem_estoque)
                messagebox.showerror("Estoque insuficiente", "Não há garrafas fechadas suficientes:\n" + detalhes)
                return
            autorizadas = []
            if a_abrir:
                detalhes = "\n".join(f"• {p['nome']}: abrir {p['garrafas_necessarias']} garrafa(s)" for p in a_abrir)
                if not messagebox.askyesno("Confirmar abertura de garrafas", "As doses das garrafas abertas não cobrem esta venda.\n\n" + detalhes + "\n\nConfirmar a abertura e concluir a venda?"):
                    return
                autorizadas = [p["produto_id"] for p in a_abrir]

            forma = self.forma_pagamento.get()
            pagamentos = None
            if status == "finalizado":
                from ui.components.payment_dialog import coletar_pagamentos
                pagamentos = coletar_pagamentos(self, total_final, forma)
                if pagamentos is None:
                    return
            observacao = self.campo_obs.get().strip() or None
            venda_id = database.registrar_venda_completa(
                itens_para_venda, forma, pct_geral, status, dia_id, observacao,
                garrafas_autorizadas=autorizadas, pagamentos=pagamentos,
                cliente_nome=cliente or None
            )
            rotulo = "FIADO" if status == "pendente" else "FINALIZADA"
            messagebox.showinfo("Venda registrada", f"Venda {venda_id} — {rotulo}\nTotal: R$ {total_final:.2f}")
            self.carrinho.clear()
            self.campo_obs.delete(0, "end")
            self.campo_cliente.delete(0, "end")
            self._renderizar_carrinho()
            self._recarregar_produtos()
            self.app.atualizar_todas_abas()
        except Exception as exc:
            messagebox.showerror("Não foi possível registrar a venda", str(exc))

    def _cancelar(self):
        if self.carrinho and messagebox.askyesno("Cancelar", "Esvaziar carrinho?"):
            self.carrinho.clear()
            self._renderizar_carrinho()

    def _recarregar_produtos(self):
        # Não pré-carrega o catálogo inteiro no PDV. As sugestões consultam só
        # os primeiros resultados necessários e o scanner pesquisa pelo código.
        self._cache = []
        self.autocomplete.set("")
