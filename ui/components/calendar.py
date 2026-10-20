import customtkinter as ctk
from typing import Optional
from datetime import date, datetime, timedelta
from ui.theme import COR, RAIO_BOTAO
from ui.components.widgets import habilitar_foco_teclado, focar_controle


class CalendarioPopup(ctk.CTkToplevel):
    """Popup modal com grade mensal de dias."""
    _MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
              "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    _DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

    def __init__(self, master, data_inicial: date | datetime | None, on_select):
        super().__init__(master)
        self.title("Selecionar Data")
        self.geometry("380x400")
        self.resizable(False, False)
        self.configure(fg_color=COR["card"])
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.on_select = on_select
        data_base = data_inicial.date() if isinstance(data_inicial, datetime) else data_inicial
        self._data_selecionada = data_base or datetime.now().date()
        self._data_ref = self._data_selecionada.replace(day=1)
        self._botoes_dia = {}
        self._construir()
        self._centralizar(master)
        self.after_idle(lambda: focar_controle(self._botoes_dia.get(self._data_selecionada)))

        self.bind("<Escape>", lambda _: self.destroy())

    def _centralizar(self, master):
        self.update_idletasks()
        topo = master.winfo_toplevel()
        x = topo.winfo_rootx() + max(0, (topo.winfo_width() - 380) // 2)
        y = topo.winfo_rooty() + max(0, (topo.winfo_height() - 400) // 2)
        self.geometry(f"+{x}+{y}")

    def _construir(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkButton(header, text="◀", width=36, height=32, corner_radius=RAIO_BOTAO,
                      fg_color=COR["azul"], hover_color=COR["azul_h"],
                      command=self._mes_anterior).pack(side="left")
        self.lbl_mes = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=14, weight="bold"),
                                     text_color=COR["dourado"])
        self.lbl_mes.pack(side="left", expand=True)
        ctk.CTkButton(header, text="▶", width=36, height=32, corner_radius=RAIO_BOTAO,
                      fg_color=COR["azul"], hover_color=COR["azul_h"],
                      command=self._mes_proximo).pack(side="right")

        dow = ctk.CTkFrame(self, fg_color="transparent")
        dow.pack(fill="x", padx=12)
        for i, d in enumerate(self._DIAS_SEMANA):
            dow.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(dow, text=d, text_color=COR["cinza"],
                         font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=i, sticky="ew")

        self.grid_dias = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_dias.pack(fill="both", expand=True, padx=12, pady=(4, 6))
        for i in range(7):
            self.grid_dias.grid_columnconfigure(i, weight=1)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(botoes, text="Hoje", corner_radius=RAIO_BOTAO,
                      fg_color=COR["roxo"], command=self._selecionar_hoje).pack(side="left")
        ctk.CTkButton(botoes, text="Cancelar", corner_radius=RAIO_BOTAO,
                      fg_color=COR["vermelho"], hover_color=COR["vermelho_h"],
                      command=self.destroy).pack(side="right")

        self._renderizar()
        habilitar_foco_teclado(self)

    def _mes_anterior(self):
        m, a = self._data_ref.month - 1, self._data_ref.year
        if m < 1:
            m, a = 12, a - 1
        self._data_ref = self._data_ref.replace(year=a, month=m)
        self._renderizar()

    def _mes_proximo(self):
        m, a = self._data_ref.month + 1, self._data_ref.year
        if m > 12:
            m, a = 1, a + 1
        self._data_ref = self._data_ref.replace(year=a, month=m)
        self._renderizar()

    def _selecionar_hoje(self):
        self.on_select(datetime.now().date())
        self.destroy()

    def _renderizar(self):
        for w in self.grid_dias.winfo_children():
            w.destroy()
        self.lbl_mes.configure(text=f"{self._MESES[self._data_ref.month - 1]} {self._data_ref.year}")

        # Domingo = 0 (weekday() do Python retorna Segunda=0)
        offset = (self._data_ref.weekday() + 1) % 7

        prox = self._data_ref.replace(day=28) + timedelta(days=4)
        ultimo = (prox - timedelta(days=prox.day)).day

        hoje = datetime.now().date()
        self._botoes_dia = {}
        col, row = offset, 0
        for dia in range(1, ultimo + 1):
            data = self._data_ref.replace(day=dia)
            if data == self._data_selecionada:
                fg = COR["vinho"]
            elif data == hoje:
                fg = COR["azul"]
            else:
                fg = COR["input"]
            btn = ctk.CTkButton(
                self.grid_dias, text=str(dia), width=36, height=32,
                corner_radius=6, fg_color=fg, hover_color=COR["hover"],
                text_color=COR["texto"], font=ctk.CTkFont(size=11),
                command=lambda d=data: self._selecionar(d)
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            movimentos = {
                "<Left>": -1, "<Right>": 1, "<Up>": -7, "<Down>": 7,
            }
            for evento, delta in movimentos.items():
                handler = lambda _e, d=data, deslocamento=delta: self._navegar_dias(d, deslocamento)
                btn.bind(evento, handler, add="+")
                canvas = getattr(btn, "_canvas", None)
                if canvas is not None:
                    canvas.bind(evento, handler, add="+")
            self._botoes_dia[data] = btn
            col += 1
            if col > 6:
                col, row = 0, row + 1
        habilitar_foco_teclado(self.grid_dias)

    def _navegar_dias(self, data_atual: date, deslocamento: int):
        alvo = data_atual + timedelta(days=deslocamento)
        self._data_selecionada = alvo
        if alvo.month != self._data_ref.month or alvo.year != self._data_ref.year:
            self._data_ref = alvo.replace(day=1)
            self._renderizar()
        botao = self._botoes_dia.get(alvo)
        if botao is not None:
            self.after_idle(lambda b=botao: focar_controle(b))
        return "break"

    def _selecionar(self, data):
        self.on_select(data)
        self.destroy()

class SeletorData(ctk.CTkFrame):
    """Botão de seleção de data + botão limpar."""
    def __init__(self, master, on_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_change = on_change
        self.data_selecionada = None  # datetime.date

        self.btn = ctk.CTkButton(
            self, text="📅 Escolher data", width=160, corner_radius=RAIO_BOTAO,
            fg_color=COR["azul"], hover_color=COR["azul_h"], command=self._abrir
        )
        self.btn.pack(side="left")

        self.btn_limpar = ctk.CTkButton(
            self, text="Limpar", width=70, corner_radius=RAIO_BOTAO,
            fg_color=COR["vermelho"], hover_color=COR["vermelho_h"], command=self.limpar
        )

    def _abrir(self):
        CalendarioPopup(self, self.data_selecionada, self._definir)

    def _definir(self, data):
        self.data_selecionada = data
        self.btn.configure(text=f"📅 {data.strftime('%d/%m/%Y')}")
        if not self.btn_limpar.winfo_ismapped():
            self.btn_limpar.pack(side="left", padx=(5, 0))
        if self.on_change:
            self.on_change()

    def limpar(self):
        self.data_selecionada = None
        self.btn.configure(text="📅 Escolher data")
        self.btn_limpar.pack_forget()
        if self.on_change:
            self.on_change()

    def get_data_str(self) -> str | None:
        return self.data_selecionada.strftime("%d/%m/%Y") if self.data_selecionada else None
