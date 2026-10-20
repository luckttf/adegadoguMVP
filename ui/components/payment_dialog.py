"""Diálogo de recebimento: aceita pagamento único ou dividido."""
from decimal import Decimal, ROUND_HALF_UP
from tkinter import messagebox
import customtkinter as ctk
from ui.theme import COR
from ui.components.widgets import habilitar_foco_teclado

FORMAS = ["Dinheiro", "Cartão", "Pix", "Misto"]
CENTAVO = Decimal("0.01")


def coletar_pagamentos(master, total: float, forma_padrao: str = "Dinheiro", *, forcar_dialogo: bool = False):
    total_d = Decimal(str(total)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if total_d < 0:
        raise ValueError("O total não pode ser negativo.")
    if total_d == 0:
        return []
    if not forcar_dialogo and forma_padrao in FORMA_UNICA:
        return [{"forma_pagamento": forma_padrao, "valor": float(total_d)}]

    janela = ctk.CTkToplevel(master)
    janela.title("Receber pagamento")
    janela.geometry("440x410")
    janela.resizable(False, False)
    janela.configure(fg_color=COR["card"])
    janela.transient(master.winfo_toplevel())
    janela.grab_set()
    resultado = {"pagamentos": None}

    ctk.CTkLabel(janela, text="Pagamento da venda", font=ctk.CTkFont(size=20, weight="bold"),
                 text_color=COR["dourado"]).pack(pady=(20, 4))
    ctk.CTkLabel(janela, text=f"Total a receber: R$ {total_d:.2f}", font=ctk.CTkFont(size=16, weight="bold"),
                 text_color=COR["texto"]).pack(pady=(0, 14))
    ctk.CTkLabel(janela, text="Forma de pagamento", text_color=COR["cinza"]).pack(anchor="w", padx=24)
    cmb = ctk.CTkComboBox(janela, values=FORMAS, state="readonly", fg_color=COR["input"],
                          border_color=COR["borda_azul"])
    cmb.set(forma_padrao if forma_padrao in FORMAS else "Dinheiro")
    cmb.pack(fill="x", padx=24, pady=(3, 10))

    frame_misto = ctk.CTkFrame(janela, fg_color="transparent")
    entries = {}
    for metodo in FORMA_UNICA:
        linha = ctk.CTkFrame(frame_misto, fg_color="transparent")
        linha.pack(fill="x", pady=3)
        ctk.CTkLabel(linha, text=metodo, width=100, anchor="w", text_color=COR["texto"]).pack(side="left")
        ent = ctk.CTkEntry(linha, placeholder_text="0,00", fg_color=COR["input"], border_color=COR["borda"])
        ent.insert(0, "0,00")
        ent.pack(side="right", fill="x", expand=True)
        entries[metodo] = ent

    def alternar(*_):
        if cmb.get() == "Misto":
            frame_misto.pack(fill="x", padx=24, pady=(0, 6))
        else:
            frame_misto.pack_forget()

    cmb.configure(command=alternar)
    alternar()

    def confirmar():
        forma = cmb.get()
        if forma in FORMA_UNICA:
            resultado["pagamentos"] = [{"forma_pagamento": forma, "valor": float(total_d)}]
            janela.destroy()
            return
        try:
            pagamentos = []
            soma = Decimal("0.00")
            for metodo, ent in entries.items():
                valor = Decimal(ent.get().strip().replace("R$", "").replace(" ", "").replace(",", ".") or "0")
                valor = valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)
                if not valor.is_finite() or valor < 0:
                    raise ValueError
                if valor > 0:
                    pagamentos.append({"forma_pagamento": metodo, "valor": float(valor)})
                    soma += valor
            if soma != total_d:
                messagebox.showerror("Valores divergentes", f"A soma informada é R$ {soma:.2f}; precisa ser R$ {total_d:.2f}.", parent=janela)
                return
            if not pagamentos:
                messagebox.showerror("Pagamento vazio", "Informe pelo menos um valor maior que zero.", parent=janela)
                return
            resultado["pagamentos"] = pagamentos
            janela.destroy()
        except (ValueError, ArithmeticError):
            messagebox.showerror("Valor inválido", "Informe valores monetários válidos.", parent=janela)

    botoes = ctk.CTkFrame(janela, fg_color="transparent")
    botoes.pack(side="bottom", fill="x", padx=24, pady=18)
    ctk.CTkButton(botoes, text="Cancelar", fg_color=COR["vermelho"], hover_color=COR["vermelho_h"],
                  command=janela.destroy).pack(side="left")
    ctk.CTkButton(botoes, text="Confirmar recebimento", fg_color=COR["verde"], hover_color=COR["verde_h"],
                  command=confirmar).pack(side="right")
    habilitar_foco_teclado(janela)
    janela.after_idle(cmb.focus_set)
    janela.bind("<Escape>", lambda _e: janela.destroy())
    master.wait_window(janela)
    return resultado["pagamentos"]


FORMA_UNICA = ["Dinheiro", "Cartão", "Pix"]
