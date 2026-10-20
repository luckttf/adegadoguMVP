import customtkinter as ctk
from tkinter import messagebox, simpledialog
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO

from ui.components.widgets import StatusDot, AutocompleteEntry, debounce_widget, habilitar_foco_teclado
from ui.components.page_header import construir_cabecalho


class PaginaEstoque(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        self._construir()
        self.atualizar_lista()

    def _construir(self):
        construir_cabecalho(
            self,
            "Estoque",
            "Acompanhe níveis, preços e disponibilidade. As ações de abertura e movimentação ficam registradas no histórico.",
        )

        barra = ctk.CTkFrame(
            self, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        barra.pack(fill="x", padx=20, pady=(0, 8))

        self.campo_busca = ctk.CTkEntry(
            barra, placeholder_text="Buscar produto por nome ou código...", width=280,
            fg_color=COR["input"], text_color=COR["texto"],
            border_color=COR["borda"], height=36,
        )
        self.campo_busca.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=10)
        self.campo_busca.bind(
            "<KeyRelease>",
            debounce_widget(self.campo_busca, self.atualizar_lista, delay_ms=180),
        )

        ctk.CTkButton(
            barra, text="Garrafas abertas", width=125,
            command=self._mostrar_garrafas_abertas, corner_radius=RAIO_BOTAO,
            fg_color=COR["superficie"], hover_color=COR["hover"], text_color=COR["texto"],
            border_width=1, border_color=COR["borda"],
        ).pack(side="right", padx=(4, 10), pady=10)
        ctk.CTkButton(
            barra, text="Categorias", width=100, command=self._abrir_categorias,
            corner_radius=RAIO_BOTAO, fg_color=COR["superficie"],
            hover_color=COR["hover"], text_color=COR["texto"],
            border_width=1, border_color=COR["borda"],
        ).pack(side="right", padx=4, pady=10)
        ctk.CTkButton(
            barra, text="Novo produto", width=120, command=self._novo_produto,
            corner_radius=RAIO_BOTAO, fg_color=COR["verde"],
            hover_color=COR["verde_h"],
        ).pack(side="right", padx=4, pady=10)
        ctk.CTkButton(
            barra, text="Movimentar", width=110, command=self._abrir_movimentacao,
            corner_radius=RAIO_BOTAO, fg_color=COR["azul"],
            hover_color=COR["azul_h"],
        ).pack(side="right", padx=4, pady=10)

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=20, pady=(0, 8))
        self.lbl_total = self._card(cards, "Produtos", COR["dourado"])
        self.lbl_ok = self._card(cards, "Estoque normal", COR["verde"])
        self.lbl_medio = self._card(cards, "Atenção", COR["amarelo"])
        self.lbl_baixo = self._card(cards, "Estoque baixo", COR["laranja"])
        self.lbl_zerado = self._card(cards, "Esgotados", COR["vermelho"])

        self.frame_lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.frame_lista.pack(fill="both", expand=True, padx=17, pady=(0, 10))

    def _card(self, pai, texto, cor):
        card = ctk.CTkFrame(
            pai, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        card.pack(side="left", expand=True, fill="x", padx=3)
        ctk.CTkLabel(
            card, text=texto, font=ctk.CTkFont(size=10), text_color=COR["cinza"],
        ).pack(anchor="w", padx=12, pady=(9, 0))
        lbl = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=19, weight="bold"), text_color=cor)
        lbl.pack(anchor="w", padx=12, pady=(1, 9))
        return lbl

    def _obter_status(self, p):
        qtd = p["quantidade"]
        if qtd == 0:
            return "Esgotado", COR["vermelho"]
        elif qtd <= p.get("estoque_minimo", 5):
            return "Baixo", COR["laranja"]
        elif qtd <= p.get("estoque_medio", 15):
            return "Médio", COR["amarelo"]
        return "Normal", COR["verde"]

    def atualizar_lista(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()
        produtos = database.buscar_produtos(self.campo_busca.get())
        total = len(produtos)
        ok = medio = baixo = zerado = 0

        for p in produtos:
            status, cor = self._obter_status(p)
            if status == "Normal": ok += 1
            elif status == "Médio": medio += 1
            elif status == "Baixo": baixo += 1
            else: zerado += 1

            frame = ctk.CTkFrame(
                self.frame_lista, fg_color=COR["card"], corner_radius=RAIO_CARD,
                border_width=1, border_color=COR["borda"],
            )
            frame.pack(fill="x", padx=3, pady=3)

            dot = StatusDot(frame, cor, tamanho=10)
            dot.pack(side="left", padx=(12, 8), pady=12)

            detalhes = ctk.CTkFrame(frame, fg_color="transparent")
            detalhes.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=8)
            ctk.CTkLabel(
                detalhes, text=p["nome"], font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COR["texto"], anchor="w",
            ).pack(anchor="w")

            info = f"Estoque: {p['quantidade']}  ·  Venda: R$ {float(p.get('preco') or 0):.2f}"
            if p.get("is_garrafa"):
                info += f"  ·  Dose: R$ {float(p.get('preco_dose') or 0):.2f}  ·  Rendimento: {float(p.get('doses_por_garrafa') or 0):.1f}"
            ctk.CTkLabel(
                detalhes, text=info, text_color=COR["cinza"], font=ctk.CTkFont(size=11),
                anchor="w", wraplength=760, justify="left",
            ).pack(anchor="w", pady=(3, 0))

            status_frame = ctk.CTkFrame(frame, fg_color=COR["superficie"], corner_radius=8)
            status_frame.pack(side="right", padx=(4, 10), pady=10)
            ctk.CTkLabel(
                status_frame, text=status, text_color=cor,
                font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(padx=9, pady=5)

            if p.get("is_garrafa") and p["quantidade"] > 0:
                ctk.CTkButton(
                    frame, text="Abrir garrafa", width=112,
                    command=lambda prod=p: self._abrir_garrafa_manual(prod),
                    corner_radius=RAIO_BOTAO, fg_color=COR["azul"], hover_color=COR["azul_h"],
                ).pack(side="right", padx=4, pady=8)

        self.lbl_total.configure(text=str(total))
        self.lbl_ok.configure(text=str(ok))
        self.lbl_medio.configure(text=str(medio))
        self.lbl_baixo.configure(text=str(baixo))
        self.lbl_zerado.configure(text=str(zerado))
        habilitar_foco_teclado(self.frame_lista)

    def _abrir_garrafa_manual(self, produto):
        if not messagebox.askyesno("Abrir garrafa",
                                    f"Deseja abrir uma garrafa de '{produto['nome']}'?\n"
                                    f"Isso consumirá 1 unidade do estoque e gerará "
                                    f"{produto.get('doses_por_garrafa', 5.7):.1f} doses."):
            return
        try:
            ok, msg, _ = database.abrir_garrafa(produto["id"])
            if ok:
                messagebox.showinfo("Sucesso", msg)
            else:
                messagebox.showerror("Erro", msg)
        except Exception as e:
            messagebox.showerror("Erro", str(e))
        self.atualizar_lista()
        self.app.atualizar_todas_abas()

    def _mostrar_garrafas_abertas(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Garrafas Abertas")
        janela.geometry("820x480")
        janela.configure(fg_color=COR["card"])
        janela.grab_set()

        ctk.CTkLabel(janela, text="Garrafas Abertas", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COR["dourado"]).pack(pady=(20, 10))

        frame_lista = ctk.CTkScrollableFrame(janela, fg_color=COR["fundo"])
        frame_lista.pack(padx=20, pady=10, fill="both", expand=True)

        def recarregar():
            for w in frame_lista.winfo_children():
                w.destroy()
            abertas = database.obter_garrafas_abertas()
            if not abertas:
                ctk.CTkLabel(frame_lista, text="Nenhuma garrafa aberta.", text_color=COR["cinza"]).pack(pady=20)
                habilitar_foco_teclado(janela)
                return
            for g in abertas:
                f = ctk.CTkFrame(frame_lista, fg_color=COR["input"], corner_radius=RAIO_BOTAO)
                f.pack(fill="x", padx=5, pady=3)

                ctk.CTkLabel(f, text=g["nome_produto"], font=ctk.CTkFont(weight="bold"),
                             text_color=COR["texto"]).pack(side="left", padx=10, pady=6)
                perdas_txt = f" | Perdas: {g.get('perdas_doses', 0):.1f}" if g.get("perdas_doses", 0) > 0 else ""
                ctk.CTkLabel(f, text=f"Aberta: {g['data_abertura']} | Restantes: {g['doses_restantes']:.1f}{perdas_txt}",
                             text_color=COR["cinza"]).pack(side="left", padx=10)

                ctk.CTkButton(f, text="Perda", width=60, corner_radius=RAIO_BOTAO,
                              command=lambda ga=g: self._registrar_perda(ga, recarregar),
                              fg_color=COR["laranja"], hover_color=COR["amarelo"]).pack(side="right", padx=4, pady=4)
                ctk.CTkButton(f, text="Ajustar", width=70, corner_radius=RAIO_BOTAO,
                              command=lambda ga=g: self._ajustar_doses(ga, recarregar),
                              fg_color=COR["azul"], hover_color=COR["azul_h"]).pack(side="right", padx=4, pady=4)
                ctk.CTkButton(f, text="Fechar", width=60, corner_radius=RAIO_BOTAO,
                              command=lambda ga=g: self._fechar_garrafa_aberta(ga, recarregar),
                              fg_color=COR["vermelho"], hover_color=COR["vermelho_h"]).pack(side="right", padx=4, pady=4)
            habilitar_foco_teclado(janela)

        recarregar()

    def _ajustar_doses(self, garrafa, callback_recarregar):
        nova = simpledialog.askfloat("Ajustar doses",
                                      f"Doses restantes para '{garrafa['nome_produto']}':",
                                      initialvalue=garrafa["doses_restantes"], minvalue=0)
        if nova is not None:
            ok, msg = database.ajustar_doses_restantes(garrafa["id"], nova)
            if ok:
                messagebox.showinfo("OK", msg)
                callback_recarregar()
                self.atualizar_lista()
                self.app.atualizar_todas_abas()
            else:
                messagebox.showerror("Erro", msg)

    def _registrar_perda(self, garrafa, callback_recarregar):
        qtd = simpledialog.askfloat("Registrar perda",
                                     f"Quantas doses de '{garrafa['nome_produto']}' foram perdidas?\n"
                                     f"(evaporação, descarte, erro de preparo etc.)",
                                     initialvalue=0.0, minvalue=0)
        if qtd is None or qtd <= 0:
            return
        motivo = simpledialog.askstring("Motivo", "Motivo da perda (opcional):") or "Perda/descarte"
        ok, msg = database.registrar_perda_dose(garrafa["id"], qtd, motivo)
        if ok:
            messagebox.showinfo("OK", msg)
            callback_recarregar()
            self.atualizar_lista()
            self.app.atualizar_todas_abas()
        else:
            messagebox.showerror("Erro", msg)

    def _fechar_garrafa_aberta(self, garrafa, callback_recarregar):
        if messagebox.askyesno("Confirmar",
                                f"Fechar garrafa de '{garrafa['nome_produto']}'? As doses restantes serão perdidas."):
            ok, msg = database.fechar_garrafa(garrafa["id"])
            if ok:
                messagebox.showinfo("OK", msg)
                callback_recarregar()
                self.atualizar_lista()
                self.app.atualizar_todas_abas()
            else:
                messagebox.showerror("Erro", msg)

    def _abrir_movimentacao(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Movimentação de Estoque")
        janela.geometry("480x300")
        janela.configure(fg_color=COR["card"])
        janela.grab_set()

        ctk.CTkLabel(janela, text="Movimentação Rápida", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COR["dourado"]).pack(pady=(20, 10))

        frame_prod = ctk.CTkFrame(janela, fg_color="transparent")
        frame_prod.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_prod, text="Produto:", text_color=COR["texto"]).pack(side="left", padx=(0, 5))

        def _sugestoes(termo):
            prods = database.buscar_produtos(termo)
            return [f"{p['nome']} — Qtd: {p['quantidade']}" for p in prods]

        autocomplete_mov = AutocompleteEntry(frame_prod, items_callback=_sugestoes, max_items=6)
        autocomplete_mov.pack(side="left", fill="x", expand=True)

        frame_qtd = ctk.CTkFrame(janela, fg_color="transparent")
        frame_qtd.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_qtd, text="Quantidade:", text_color=COR["texto"]).pack(side="left", padx=(0, 5))
        entry_qtd_mov = ctk.CTkEntry(frame_qtd, width=100, fg_color=COR["input"],
                                      text_color=COR["texto"], border_color=COR["borda_azul"])
        entry_qtd_mov.insert(0, "1")
        entry_qtd_mov.pack(side="left")

        def executar(tipo):
            nome_selecionado = autocomplete_mov.get_selected_product_name()
            if not nome_selecionado:
                messagebox.showwarning("Aviso", "Selecione um produto.")
                return
            produtos = database.buscar_produtos(nome_selecionado)
            produto = next((p for p in produtos if p["nome"] == nome_selecionado), None)
            if not produto:
                messagebox.showerror("Erro", "Produto não encontrado.")
                return
            try:
                qtd = int(entry_qtd_mov.get().strip())
            except ValueError:
                messagebox.showerror("Erro", "Quantidade inválida.")
                return
            if qtd <= 0:
                messagebox.showerror("Erro", "Quantidade deve ser positiva.")
                return
            if tipo == "entrada":
                ok, msg = database.registrar_entrada(produto["id"], qtd)
            else:
                ok, msg = database.registrar_saida(produto["id"], qtd)
            if ok:
                messagebox.showinfo("Sucesso", msg)
                self.atualizar_lista()
                self.app.atualizar_todas_abas()
                janela.destroy()
            else:
                messagebox.showerror("Erro", msg)

        botoes = ctk.CTkFrame(janela, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=20)
        ctk.CTkButton(botoes, text="Entrada", width=130, corner_radius=RAIO_BOTAO,
                      command=lambda: executar("entrada"),
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(side="left", padx=10)
        ctk.CTkButton(botoes, text="Saída", width=130, corner_radius=RAIO_BOTAO,
                      command=lambda: executar("saida"),
                      fg_color=COR["vermelho"], hover_color=COR["vermelho_h"]).pack(side="right", padx=10)
        habilitar_foco_teclado(janela)
        janela.after_idle(autocomplete_mov.entry.focus_set)

    def _abrir_form_produto(self, janela, produto=None):
        frame = ctk.CTkFrame(janela, fg_color="transparent")
        frame.pack(padx=20, fill="x", pady=10)

        cats = database.obter_categorias_unicas()
        widgets = {}

        def linha(label, valor_inicial="", row=0):
            ctk.CTkLabel(frame, text=label, text_color=COR["texto"]).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            entry = ctk.CTkEntry(frame, width=250, fg_color=COR["input"],
                                  text_color=COR["texto"], border_color=COR["borda_azul"])
            if valor_inicial:
                entry.insert(0, str(valor_inicial))
            entry.grid(row=row, column=1, sticky="w", padx=10, pady=4)
            return entry

        r = 0
        widgets["Nome:"] = linha("Nome:", produto["nome"] if produto else "", r); r += 1

        ctk.CTkLabel(frame, text="Categoria:", text_color=COR["texto"]).grid(row=r, column=0, sticky="w", padx=10, pady=4)
        combo_cat = ctk.CTkComboBox(frame, values=cats or ["Geral"], width=250,
                                     fg_color=COR["input"], border_color=COR["borda_azul"])
        valor_cat = produto.get("categoria", "") if produto else ""
        combo_cat.set(valor_cat if valor_cat in cats else (cats[0] if cats else "Geral"))
        combo_cat.grid(row=r, column=1, sticky="w", padx=10, pady=4)
        widgets["Categoria:"] = combo_cat
        r += 1

        widgets["Quantidade:"] = linha("Quantidade:", produto["quantidade"] if produto else "0", r); r += 1
        widgets["Preço Venda (R$):"] = linha("Preço Venda (R$):",
                                              f"{produto['preco']:.2f}" if produto else "", r); r += 1
        widgets["Preço Custo (R$):"] = linha("Preço Custo (R$):",
                                              f"{produto.get('preco_custo', 0):.2f}" if produto else "0.0", r); r += 1
        widgets["Cód.Barras:"] = linha("Cód.Barras:", produto.get("codigo_barras", "") if produto else "", r); r += 1
        widgets["Estoque Mínimo:"] = linha("Estoque Mínimo:",
                                            produto.get("estoque_minimo", 5) if produto else "5", r); r += 1
        widgets["Estoque Médio:"] = linha("Estoque Médio:",
                                           produto.get("estoque_medio", 15) if produto else "15", r); r += 1

        var_garrafa = ctk.BooleanVar(value=bool(produto.get("is_garrafa")) if produto else False)
        chk_garrafa = ctk.CTkCheckBox(frame, text="🍾 É garrafa (permite venda por dose)",
                                       variable=var_garrafa, text_color=COR["texto"],
                                       fg_color=COR["vinho"], hover_color=COR["vinho_h"],
                                       command=lambda: alternar_campos_dose())
        chk_garrafa.grid(row=r, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))
        r += 1

        frame_dose = ctk.CTkFrame(frame, fg_color=COR["input"], corner_radius=RAIO_BOTAO)
        frame_dose.grid(row=r, column=0, columnspan=2, sticky="we", padx=10, pady=4)
        r += 1

        volume_inicial = produto.get("volume_garrafa_ml", database.VOLUME_GARRAFA_ML_PADRAO) if produto else database.VOLUME_GARRAFA_ML_PADRAO
        _, doses_sugeridas = database.calcular_doses_estimadas(volume_inicial)
        doses_inicial = produto.get("doses_por_garrafa", doses_sugeridas) if produto else doses_sugeridas
        preco_dose_inicial = produto.get("preco_dose", 0.0) if produto else 0.0

        ctk.CTkLabel(frame_dose, text="Volume da garrafa (ml):", text_color=COR["texto"]).grid(
            row=0, column=0, sticky="w", padx=8, pady=4)
        entry_volume = ctk.CTkEntry(frame_dose, width=100, fg_color=COR["card"], text_color=COR["texto"])
        entry_volume.insert(0, str(volume_inicial))
        entry_volume.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ctk.CTkLabel(frame_dose, text="Doses por garrafa:", text_color=COR["texto"]).grid(
            row=1, column=0, sticky="w", padx=8, pady=4)
        entry_doses = ctk.CTkEntry(frame_dose, width=100, fg_color=COR["card"], text_color=COR["texto"])
        entry_doses.insert(0, f"{doses_inicial:.2f}")
        entry_doses.grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ctk.CTkLabel(frame_dose, text="Preço da Dose (R$):", text_color=COR["texto"]).grid(
            row=2, column=0, sticky="w", padx=8, pady=4)
        entry_preco_dose = ctk.CTkEntry(frame_dose, width=100, fg_color=COR["card"], text_color=COR["texto"])
        entry_preco_dose.insert(0, f"{preco_dose_inicial:.2f}")
        entry_preco_dose.grid(row=2, column=1, sticky="w", padx=8, pady=4)

        def recalcular_sugestao():
            try:
                vol = float(entry_volume.get().replace(",", "."))
            except ValueError:
                return
            _, sugestao = database.calcular_doses_estimadas(vol)
            entry_doses.delete(0, "end")
            entry_doses.insert(0, f"{sugestao:.2f}")

        ctk.CTkButton(frame_dose, text="Recalcular sugestão", width=140, corner_radius=RAIO_BOTAO,
                      fg_color=COR["roxo"], command=recalcular_sugestao).grid(row=0, column=2, padx=8, pady=4)

        def alternar_campos_dose():
            if var_garrafa.get():
                frame_dose.grid()
            else:
                frame_dose.grid_remove()

        alternar_campos_dose()

        widgets["_var_garrafa"] = var_garrafa
        widgets["_entry_volume"] = entry_volume
        widgets["_entry_doses"] = entry_doses
        widgets["_entry_preco_dose"] = entry_preco_dose
        return widgets

    def _novo_produto(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Novo Produto")
        janela.geometry("520x680")
        janela.configure(fg_color=COR["card"])
        janela.grab_set()

        ctk.CTkLabel(janela, text="Novo Produto", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COR["dourado"]).pack(pady=(20, 10))

        widgets = self._abrir_form_produto(janela)

        def salvar():
            nome = widgets["Nome:"].get().strip()
            if not nome:
                messagebox.showwarning("Aviso", "Nome obrigatório.")
                return
            try:
                qtd = int(widgets["Quantidade:"].get() or "0")
                preco = float(widgets["Preço Venda (R$):"].get().replace(",", ".") or "0")
                custo = float(widgets["Preço Custo (R$):"].get().replace(",", ".") or "0")
                cat = widgets["Categoria:"].get()
                is_garrafa = widgets["_var_garrafa"].get()
                volume = int(float(widgets["_entry_volume"].get().replace(",", ".") or 900))
                doses = float(widgets["_entry_doses"].get().replace(",", ".") or 0) if is_garrafa else 0.0
                preco_dose = float(widgets["_entry_preco_dose"].get().replace(",", ".") or 0) if is_garrafa else 0.0
                
                # [CORREÇÃO] Lendo o código de barras e limites de estoque do formulário, em vez de fixar None, 5, 15.
                cod_barras = widgets["Cód.Barras:"].get().strip() or None
                est_min = int(widgets["Estoque Mínimo:"].get() or "5")
                est_med = int(widgets["Estoque Médio:"].get() or "15")

                ok, msg = database.adicionar_produto(
                    nome, cat, qtd, preco, cod_barras, est_min, est_med, custo,
                    is_garrafa=is_garrafa, doses_por_garrafa=doses,
                    preco_dose=preco_dose, volume_garrafa_ml=volume
                )
                if ok:
                    messagebox.showinfo("OK", f"'{nome}' cadastrado!")
                    janela.destroy()
                    self.atualizar_lista()
                    self.app.atualizar_todas_abas() # [CORREÇÃO] Atualiza a aba Banco de Produtos também
                else:
                    messagebox.showerror("Erro", msg)
            except ValueError:
                messagebox.showerror("Erro", "Valores numéricos inválidos.")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao cadastrar: {e!s}")

        ctk.CTkButton(janela, text="Salvar", command=salvar, corner_radius=RAIO_BOTAO,
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(pady=20)
        habilitar_foco_teclado(janela)
        janela.after_idle(widgets["Nome:"].focus_set)

    def _abrir_categorias(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Categorias")
        janela.geometry("400x400")
        janela.configure(fg_color=COR["card"])
        janela.grab_set()

        ctk.CTkLabel(janela, text="Categorias", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COR["dourado"]).pack(pady=(20, 10))

        frame_lista = ctk.CTkScrollableFrame(janela, fg_color=COR["fundo"])
        frame_lista.pack(padx=20, pady=10, fill="both", expand=True)

        frame_add = ctk.CTkFrame(janela, fg_color="transparent")
        frame_add.pack(fill="x", padx=20, pady=10)
        entry_nova = ctk.CTkEntry(frame_add, placeholder_text="Nova categoria...",
                                   fg_color=COR["input"], text_color=COR["texto"], border_color=COR["borda_verde"])
        entry_nova.pack(side="left", padx=8, pady=8, fill="x", expand=True)

        def atualizar():
            for w in frame_lista.winfo_children():
                w.destroy()
            for cid, nome in database.obter_todas_categorias():
                f = ctk.CTkFrame(frame_lista, fg_color=COR["input"], corner_radius=RAIO_BOTAO)
                f.pack(fill="x", padx=5, pady=3)
                ctk.CTkLabel(f, text=nome, text_color=COR["texto"]).pack(side="left", padx=10, pady=6)
                ctk.CTkButton(f, text="X", width=40, corner_radius=RAIO_BOTAO,
                              fg_color=COR["vermelho"], hover_color=COR["vermelho_h"],
                              command=lambda c=cid: (database.remover_categoria(c), atualizar())).pack(
                    side="right", padx=3, pady=4)
            habilitar_foco_teclado(janela)

        ctk.CTkButton(frame_add, text="Adicionar", corner_radius=RAIO_BOTAO,
                      command=lambda: (database.adicionar_categoria(entry_nova.get().strip()),
                                        entry_nova.delete(0, "end"), atualizar())
                      if entry_nova.get().strip() else None,
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(side="right", padx=8, pady=8)
        atualizar()
        habilitar_foco_teclado(janela)
        janela.after_idle(entry_nova.focus_set)