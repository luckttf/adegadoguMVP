import customtkinter as ctk
from tkinter import messagebox, filedialog
import database
from ui.theme import COR, RAIO_CARD, RAIO_BOTAO

from ui.components.widgets import debounce_widget, habilitar_foco_teclado
from ui.components.page_header import construir_cabecalho


class PaginaBanco(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COR["fundo"])
        self.app = app
        self._construir()
        self.atualizar_lista()

    def _construir(self):
        construir_cabecalho(
            self,
            "Banco de produtos",
            "Catálogo central de preços, custos, códigos de barras e configurações de doses.",
        )

        topo = ctk.CTkFrame(
            self, fg_color=COR["card"], corner_radius=RAIO_CARD,
            border_width=1, border_color=COR["borda"],
        )
        topo.pack(fill="x", padx=20, pady=(0, 10))

        self.campo_filtro = ctk.CTkEntry(
            topo, placeholder_text="Buscar nome, categoria ou código de barras...", width=300,
            fg_color=COR["input"], text_color=COR["texto"],
            border_color=COR["borda"], height=36,
        )
        self.campo_filtro.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=10)
        self.campo_filtro.bind(
            "<KeyRelease>", debounce_widget(self.campo_filtro, self.atualizar_lista, delay_ms=180),
        )
        self.campo_filtro.bind("<Return>", lambda _: self.atualizar_lista())

        ctk.CTkButton(
            topo, text="Arquivados", width=100, command=self._mostrar_arquivados,
            corner_radius=RAIO_BOTAO, fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"], border_width=1, border_color=COR["borda"],
        ).pack(side="right", padx=4, pady=10)
        ctk.CTkButton(
            topo, text="Importar CSV", width=112, command=self._importar,
            corner_radius=RAIO_BOTAO, fg_color=COR["azul"], hover_color=COR["azul_h"],
        ).pack(side="right", padx=4, pady=10)
        ctk.CTkButton(
            topo, text="Novo produto", width=118, command=self._novo,
            corner_radius=RAIO_BOTAO, fg_color=COR["verde"], hover_color=COR["verde_h"],
        ).pack(side="right", padx=(4, 10), pady=10)

        self.lbl_resultados = ctk.CTkLabel(
            self, text="", text_color=COR["cinza"], font=ctk.CTkFont(size=11), anchor="w",
        )
        self.lbl_resultados.pack(fill="x", padx=22, pady=(0, 4))

        self.frame_lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.frame_lista.pack(fill="both", expand=True, padx=17, pady=(0, 10))

    def atualizar_lista(self):
        for w in self.frame_lista.winfo_children():
            w.destroy()
        produtos = database.buscar_produtos(self.campo_filtro.get())
        self.lbl_resultados.configure(text=f"{len(produtos)} produto(s) encontrado(s)")
        if not produtos:
            ctk.CTkLabel(
                self.frame_lista, text="Nenhum produto encontrado. Ajuste a busca ou cadastre um novo item.",
                text_color=COR["cinza"], font=ctk.CTkFont(size=12),
            ).pack(pady=38)
            return

        for p in produtos:
            frame = ctk.CTkFrame(
                self.frame_lista, fg_color=COR["card"], corner_radius=RAIO_CARD,
                border_width=1, border_color=COR["borda"],
            )
            frame.pack(fill="x", padx=3, pady=3)

            detalhes = ctk.CTkFrame(frame, fg_color="transparent")
            detalhes.pack(side="left", fill="x", expand=True, padx=13, pady=10)
            ctk.CTkLabel(
                detalhes, text=p["nome"], font=ctk.CTkFont(size=13, weight="bold"),
                text_color=COR["texto"], anchor="w",
            ).pack(anchor="w")
            categoria = p.get("categoria") or "Sem categoria"
            codigo = p.get("codigo_barras") or "Sem código de barras"
            ctk.CTkLabel(
                detalhes, text=f"{categoria}  ·  {codigo}", text_color=COR["cinza"],
                font=ctk.CTkFont(size=10), anchor="w",
            ).pack(anchor="w", pady=(2, 4))

            custo = float(p.get("preco_custo") or 0)
            preco = float(p.get("preco") or 0)
            lucro = preco - custo
            info = f"Venda  R$ {preco:.2f}     Custo  R$ {custo:.2f}     Lucro/un.  R$ {lucro:.2f}     Estoque  {p['quantidade']}"
            if p.get("is_garrafa"):
                rendimento = float(p.get("doses_por_garrafa") or 0)
                custo_dose = custo / rendimento if rendimento > 0 else 0.0
                lucro_dose = float(p.get("preco_dose") or 0) - custo_dose
                info += f"\nDose  R$ {float(p.get('preco_dose') or 0):.2f}     Custo/dose  R$ {custo_dose:.2f}     Lucro/dose  R$ {lucro_dose:.2f}"
            ctk.CTkLabel(
                detalhes, text=info, text_color=COR["cinza"],
                font=ctk.CTkFont(size=11), anchor="w", justify="left",
            ).pack(anchor="w")

            acoes = ctk.CTkFrame(frame, fg_color="transparent")
            acoes.pack(side="right", padx=8, pady=8)
            ctk.CTkButton(
                acoes, text="Editar", width=72, command=lambda p=p: self._editar(p),
                corner_radius=RAIO_BOTAO, fg_color=COR["azul"], hover_color=COR["azul_h"],
            ).pack(pady=(0, 5))
            ctk.CTkButton(
                acoes, text="Arquivar", width=72, command=lambda p=p: self._excluir(p),
                corner_radius=RAIO_BOTAO, fg_color=COR["superficie"],
                hover_color=COR["hover"], text_color=COR["vermelho"],
                border_width=1, border_color=COR["borda"],
            ).pack()

        habilitar_foco_teclado(self.frame_lista)

    def _editar(self, produto):
        janela = ctk.CTkToplevel(self)
        janela.title("Editar Produto")
        janela.geometry("560x760")
        janela.configure(fg_color=COR["card"])
        janela.grab_set()

        ctk.CTkLabel(janela, text="Editar Produto", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COR["dourado"]).pack(pady=(20, 10))

        widgets = self.app.pagina_estoque._abrir_form_produto(janela, produto=produto)

        def salvar():
            try:
                nome = widgets["Nome:"].get().strip()
                if not nome:
                    messagebox.showwarning("Aviso", "Nome obrigatório.")
                    return
                categoria = widgets["Categoria:"].get().strip()
                preco = float(widgets["Preço Venda (R$):"].get().replace(",", "."))
                custo = float(widgets["Preço Custo (R$):"].get().replace(",", "."))
                qtd = int(widgets["Quantidade:"].get())
                cod_barras = widgets["Cód.Barras:"].get().strip() or None
                est_min = int(widgets["Estoque Mínimo:"].get())
                est_med = int(widgets["Estoque Médio:"].get())
                is_garrafa = widgets["_var_garrafa"].get()
                volume = int(float(widgets["_entry_volume"].get().replace(",", ".") or 900))
                doses = float(widgets["_entry_doses"].get().replace(",", ".") or 0) if is_garrafa else 0.0
                preco_dose = float(widgets["_entry_preco_dose"].get().replace(",", ".") or 0) if is_garrafa else 0.0

                ok, msg = database.editar_produto_completo(
                    produto["id"], nome, categoria, preco, qtd,
                    codigo_barras=cod_barras, estoque_minimo=est_min, estoque_medio=est_med,
                    preco_custo=custo, is_garrafa=is_garrafa, doses_por_garrafa=doses,
                    preco_dose=preco_dose, volume_garrafa_ml=volume
                )
                if ok:
                    messagebox.showinfo("OK", msg)
                    janela.destroy()
                    self.atualizar_lista()
                    self.app.atualizar_todas_abas()
                else:
                    messagebox.showerror("Erro", msg)
            except Exception as e:
                messagebox.showerror("Erro", f"Valores inválidos.\n{str(e)}")

        ctk.CTkButton(janela, text="Salvar", command=salvar, corner_radius=RAIO_BOTAO,
                      fg_color=COR["verde"], hover_color=COR["verde_h"]).pack(pady=20)
        habilitar_foco_teclado(janela)
        janela.after_idle(widgets["Nome:"].focus_set)

    def _excluir(self, produto):
        if messagebox.askyesno("Arquivar produto", f"Arquivar '{produto['nome']}'? O histórico de vendas e movimentações será preservado."):
            ok, msg = database.deletar_produto(produto["id"])
            if ok:
                messagebox.showinfo("Produto arquivado", msg)
            else:
                messagebox.showerror("Não foi possível arquivar", msg)
            self.atualizar_lista()
            self.app.atualizar_todas_abas()

    def _mostrar_arquivados(self):
        """Janela dedicada a consultar e restaurar produtos arquivados."""
        janela = ctk.CTkToplevel(self)
        janela.title("Produtos arquivados | BARNS")
        janela.geometry("900x580")
        janela.minsize(720, 420)
        janela.configure(fg_color=COR["fundo"])
        janela.transient(self.winfo_toplevel())
        janela.grab_set()

        topo = ctk.CTkFrame(janela, fg_color="transparent")
        topo.pack(fill="x", padx=22, pady=(20, 8))
        ctk.CTkLabel(
            topo, text="Produtos arquivados",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=COR["texto"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            topo,
            text="Os produtos arquivados ficam fora do PDV, mas seus históricos são preservados.",
            font=ctk.CTkFont(size=12), text_color=COR["cinza"],
        ).pack(anchor="w", pady=(3, 10))

        barra = ctk.CTkFrame(janela, fg_color="transparent")
        barra.pack(fill="x", padx=22, pady=(0, 8))
        filtro = ctk.CTkEntry(
            barra, placeholder_text="Buscar por nome, categoria ou código de barras...",
            fg_color=COR["input"], text_color=COR["texto"], border_color=COR["borda"],
        )
        filtro.pack(side="left", fill="x", expand=True, padx=(0, 8))
        lista = ctk.CTkScrollableFrame(
            janela, fg_color=COR["card"], corner_radius=RAIO_CARD,
        )
        lista.pack(fill="both", expand=True, padx=22, pady=(0, 16))

        def recarregar(_event=None):
            for widget in lista.winfo_children():
                widget.destroy()
            try:
                produtos = database.listar_produtos_arquivados(filtro.get())
            except Exception as exc:
                messagebox.showerror("Erro ao consultar arquivados", str(exc), parent=janela)
                return "break"

            if not produtos:
                ctk.CTkLabel(
                    lista, text="Nenhum produto arquivado encontrado.",
                    text_color=COR["cinza"],
                ).pack(pady=35)
                return "break"

            for produto in produtos:
                linha = ctk.CTkFrame(
                    lista, fg_color=COR["superficie"], corner_radius=RAIO_BOTAO,
                    border_width=1, border_color=COR["borda"],
                )
                linha.pack(fill="x", padx=5, pady=4)
                textos = ctk.CTkFrame(linha, fg_color="transparent")
                textos.pack(side="left", fill="x", expand=True, padx=12, pady=10)
                ctk.CTkLabel(
                    textos, text=produto["nome"],
                    font=ctk.CTkFont(size=13, weight="bold"), text_color=COR["texto"],
                ).pack(anchor="w")
                detalhes = f"Estoque registrado: {produto['quantidade']}  ·  Preço: R$ {float(produto.get('preco') or 0):.2f}"
                if produto.get("categoria"):
                    detalhes += f"  ·  {produto['categoria']}"
                ctk.CTkLabel(
                    textos, text=detalhes, text_color=COR["cinza"],
                    font=ctk.CTkFont(size=11),
                ).pack(anchor="w", pady=(2, 0))

                def restaurar(p=produto):
                    if not messagebox.askyesno(
                        "Restaurar produto",
                        f"Restaurar '{p['nome']}' para o catálogo ativo e permitir novas vendas?",
                        parent=janela,
                    ):
                        return
                    ok, msg = database.restaurar_produto(p["id"])
                    if ok:
                        messagebox.showinfo("Produto restaurado", msg, parent=janela)
                        recarregar()
                        self.atualizar_lista()
                        self.app.atualizar_todas_abas()
                    else:
                        messagebox.showerror("Não foi possível restaurar", msg, parent=janela)

                ctk.CTkButton(
                    linha, text="Restaurar", width=104, height=32,
                    command=restaurar, corner_radius=RAIO_BOTAO,
                    fg_color=COR["verde"], hover_color=COR["verde_h"],
                ).pack(side="right", padx=10, pady=10)
            habilitar_foco_teclado(lista)
            return "break"

        filtro.bind("<KeyRelease>", debounce_widget(filtro, recarregar, delay_ms=160))
        filtro.bind("<Return>", recarregar)
        ctk.CTkButton(
            barra, text="Atualizar", width=92, command=recarregar,
            corner_radius=RAIO_BOTAO, fg_color=COR["azul"], hover_color=COR["azul_h"],
        ).pack(side="right")
        ctk.CTkButton(
            janela, text="Fechar", width=100, command=janela.destroy,
            corner_radius=RAIO_BOTAO, fg_color=COR["superficie"], hover_color=COR["hover"],
            text_color=COR["texto"],
        ).pack(anchor="e", padx=22, pady=(0, 16))
        habilitar_foco_teclado(janela)
        filtro.after_idle(filtro.focus_set)
        recarregar()

    def _novo(self):
        # [CORREÇÃO] Apenas abre o modal. A atualização da lista será feita
        # pelo inventory.py assim que o cadastro for salvo.
        self.app.pagina_estoque._novo_produto()

    def _importar(self):
        # [CORREÇÃO] Exibe os erros linha por linha caso a importação não seja 100%
        arquivo = filedialog.askopenfilename(title="Selecionar CSV", filetypes=[("CSV", "*.csv")])
        if arquivo:
            total, importados, erros = database.importar_csv(arquivo)
            if erros:
                detalhe = "\n".join(erros[:15])
                if len(erros) > 15:
                    detalhe += f"\n... e mais {len(erros) - 15} erro(s)."
                messagebox.showwarning("Importação com avisos", f"{importados} de {total} importados.\n\nErros:\n{detalhe}")
            else:
                messagebox.showinfo("Importação", f"{importados} de {total} importados com sucesso.")
            self.atualizar_lista()
            self.app.atualizar_todas_abas()