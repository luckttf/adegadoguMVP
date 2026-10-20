"""Persistência transacional de vendas, recebimentos e histórico."""
import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from infrastructure.database.connection import get_db
from infrastructure.database.repositories.bottles import _abrir_garrafa_na_transacao

CENTAVO = Decimal("0.01")
FORMAS_VALIDAS = {"Dinheiro", "Cartão", "Pix"}
STATUS_VALIDOS = {"finalizado", "pendente"}


def _dinheiro(valor: Any) -> Decimal:
    try:
        d = Decimal(str(valor))
    except Exception as exc:
        raise ValueError("Valor monetário inválido.") from exc
    if not d.is_finite():
        raise ValueError("O valor monetário deve ser finito.")
    return d.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _centavos(valor: Decimal) -> int:
    return int((valor / CENTAVO).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _data_agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _sort_data_sql(coluna: str = "data") -> str:
    # Compatível com datas legadas no formato dd/mm/yyyy HH:MM[:SS].
    return f"substr({coluna},7,4)||substr({coluna},4,2)||substr({coluna},1,2)||substr({coluna},12,8)"


def _data_key(data: str) -> str:
    try:
        parsed = datetime.strptime(data, "%d/%m/%Y")
        return parsed.strftime("%Y%m%d")
    except (TypeError, ValueError):
        raise ValueError("Data inválida. Use dd/mm/aaaa.")


def _validar_pagamentos(pagamentos, total: Decimal, forma_pagamento: str) -> list[dict]:
    if total < 0:
        raise ValueError("O total da venda não pode ser negativo.")
    if total == 0:
        return []
    if pagamentos is None:
        if forma_pagamento == "Misto":
            raise ValueError("Informe os valores de cada meio de pagamento para uma venda mista.")
        if forma_pagamento not in FORMAS_VALIDAS:
            raise ValueError("Forma de pagamento inválida.")
        pagamentos = [{"forma_pagamento": forma_pagamento, "valor": str(total)}]
    saida = []
    soma = 0
    for pagamento in pagamentos:
        forma = pagamento.get("forma_pagamento", pagamento.get("forma"))
        valor = _dinheiro(pagamento.get("valor", 0))
        if forma not in FORMAS_VALIDAS:
            raise ValueError(f"Meio de pagamento inválido: {forma!r}.")
        if valor < 0:
            raise ValueError("O valor de cada pagamento não pode ser negativo.")
        if valor == 0:
            continue
        soma += _centavos(valor)
        saida.append({"forma_pagamento": forma, "valor": valor})
    if soma != _centavos(total):
        raise ValueError(f"A soma dos pagamentos ({soma / 100:.2f}) precisa ser igual ao total da venda ({total:.2f}).")
    if not saida:
        raise ValueError("Informe pelo menos um pagamento positivo.")
    return saida


def _distribuir_desconto_geral(desconto_centavos: int, bases_centavos: list[int]) -> list[int]:
    """Distribui centavos proporcionalmente sem perder/arredondar valor do total."""
    if desconto_centavos <= 0:
        return [0 for _ in bases_centavos]
    total_base = sum(bases_centavos)
    if total_base <= 0:
        return [0 for _ in bases_centavos]
    exatos = [Decimal(desconto_centavos) * Decimal(base) / Decimal(total_base) for base in bases_centavos]
    partes = [int(x) for x in exatos]  # floor para valores não negativos
    sobram = desconto_centavos - sum(partes)
    ordem = sorted(range(len(exatos)), key=lambda i: exatos[i] - partes[i], reverse=True)
    for i in ordem[:sobram]:
        partes[i] += 1
    return partes


def prever_abertura_garrafas(itens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Delega prévia à regra de doses sem expor detalhes de SQL à interface."""
    from infrastructure.database.repositories.bottles import prever_abertura_garrafas as prever
    return prever(itens)


def registrar_venda_completa(itens: List[Dict], forma_pagamento: str,
                             desconto_percentual: float = 0.0, status: str = "finalizado",
                             dia_operacao_id: Optional[int] = None,
                             observacao: Optional[str] = None, *,
                             garrafas_autorizadas: Optional[List[int]] = None,
                             pagamentos: Optional[List[Dict[str, Any]]] = None,
                             cliente_nome: Optional[str] = None) -> int:
    """Registra venda + estoque + doses + pagamentos em uma transação atômica.
    
    ``pendente`` representa fiado: o produto foi entregue e baixa o estoque,
    mas não cria recebimentos até que o fiado seja quitado.
    ``garrafas_autorizadas`` é a lista de produtos para os quais o operador
    confirmou a abertura de garrafas fechadas durante esta venda.
    """
    if not isinstance(itens, list) or not itens:
        raise ValueError("Não é possível registrar uma venda sem itens.")
    if status not in STATUS_VALIDOS:
        raise ValueError("Status de venda inválido.")
    try:
        pct_geral = Decimal(str(desconto_percentual))
    except Exception as exc:
        raise ValueError("Desconto geral inválido.") from exc
    if not pct_geral.is_finite() or pct_geral < 0 or pct_geral > 100:
        raise ValueError("O desconto geral precisa estar entre 0% e 100%.")

    # Valida o conteúdo externo antes de abrir a transação.
    itens_normalizados = []
    for original in itens:
        try:
            pid = int(original["produto_id"])
            qtd_d = Decimal(str(original["quantidade"]))
            price_sent = _dinheiro(original["preco"])
            desc_pct = Decimal(str(original.get("desconto_percentual", 0)))
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            raise ValueError("Há um item de venda com campos inválidos.") from exc
        if pid <= 0 or not qtd_d.is_finite() or qtd_d <= 0:
            raise ValueError("Produto e quantidade devem ser válidos; a quantidade deve ser positiva.")
        if qtd_d != qtd_d.to_integral_value():
            raise ValueError("A quantidade vendida precisa ser um número inteiro de unidades/doses.")
        if price_sent < 0:
            raise ValueError("O preço de venda não pode ser negativo.")
        if not desc_pct.is_finite() or desc_pct < 0 or desc_pct > 100:
            raise ValueError("O desconto por item precisa estar entre 0% e 100%.")
        tipo = "dose" if original.get("tipo") == "dose" else "unidade"
        if tipo == "dose" and qtd_d != qtd_d.to_integral_value():
            raise ValueError("A quantidade de doses precisa ser inteira.")
        itens_normalizados.append({
            "produto_id": pid, "nome_fornecido": str(original.get("nome") or ""),
            "quantidade": int(qtd_d), "preco_enviado": price_sent,
            "desconto_percentual": desc_pct, "tipo": tipo,
        })

    autorizadas = {int(x) for x in (garrafas_autorizadas or [])}
    agora = _data_agora()
    with get_db() as (conn, cur):
        conn.execute("BEGIN IMMEDIATE")

        # Toda venda pertence a um dia operacional ainda aberto.
        if dia_operacao_id is None:
            dia = cur.execute("SELECT id FROM dias_operacao WHERE status='aberto' ORDER BY id DESC LIMIT 1").fetchone()
            dia_operacao_id = int(dia["id"]) if dia else None
        if dia_operacao_id is None:
            raise ValueError("Não existe dia de operação aberto. Inicie o dia antes de vender.")
        dia = cur.execute("SELECT id,status FROM dias_operacao WHERE id=?", (dia_operacao_id,)).fetchone()
        if not dia or dia["status"] != "aberto":
            raise ValueError("O dia de operação está fechado ou não existe. Abra um novo dia antes de vender.")

        # O banco é a fonte de verdade para o preço e o estado do produto.
        itens = []
        total_bruto_cents = 0
        total_desc_item_cents = 0
        for item in itens_normalizados:
            produto = cur.execute("SELECT * FROM produtos WHERE id=? AND ativo=1", (item["produto_id"],)).fetchone()
            if not produto:
                raise ValueError(f"Produto '{item['nome_fornecido']}' não encontrado ou arquivado.")
            if item["tipo"] == "dose":
                if not produto["is_garrafa"]:
                    raise ValueError(f"'{produto['nome']}' não está configurado para venda por dose.")
                preco_atual = _dinheiro(produto["preco_dose"])
            else:
                preco_atual = _dinheiro(produto["preco"])
            if item["preco_enviado"] != preco_atual:
                raise ValueError(f"O preço de '{produto['nome']}' foi alterado. Atualize o carrinho e tente novamente.")
            bruto = _dinheiro(preco_atual * item["quantidade"])
            desconto_item = _dinheiro(bruto * item["desconto_percentual"] / Decimal(100))
            bruto_c = _centavos(bruto)
            desc_c = min(_centavos(desconto_item), bruto_c)
            total_bruto_cents += bruto_c
            total_desc_item_cents += desc_c
            itens.append({
                **item, "produto": produto, "nome": item["nome_fornecido"] or produto["nome"],
                "preco": preco_atual, "bruto_cents": bruto_c,
                "desconto_item_cents": desc_c, "base_apos_desconto_cents": bruto_c-desc_c,
            })

        base_apos_item = total_bruto_cents - total_desc_item_cents
        desconto_geral_cents = int((Decimal(base_apos_item) * pct_geral / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        desconto_geral_cents = max(0, min(desconto_geral_cents, base_apos_item))
        parcelas_gerais = _distribuir_desconto_geral(desconto_geral_cents, [i["base_apos_desconto_cents"] for i in itens])
        total_liquido_cents = 0
        for item, allocated in zip(itens, parcelas_gerais):
            item["desconto_geral_rateado_cents"] = allocated
            item["liquido_cents"] = max(0, item["base_apos_desconto_cents"] - allocated)
            total_liquido_cents += item["liquido_cents"]
        total_final = (Decimal(total_liquido_cents) * CENTAVO).quantize(CENTAVO)

        cliente_nome = (cliente_nome or "").strip() or None
        if status == "pendente":
            if not cliente_nome:
                raise ValueError("Informe o nome do cliente para registrar uma venda fiada.")
            if pagamentos:
                raise ValueError("Uma venda fiada não pode registrar pagamento nesta etapa; registre o recebimento ao quitar.")
            pagamentos_registrados = []
            forma_final = "Fiado"
        else:
            pagamentos_registrados = _validar_pagamentos(pagamentos, total_final, forma_pagamento)
            if pagamentos is not None:
                formas = {p["forma_pagamento"] for p in pagamentos_registrados}
                forma_final = next(iter(formas)) if len(formas) == 1 else "Misto"
            else:
                forma_final = forma_pagamento

        # Pré-validar toda a demanda de doses dentro da transação.
        demand_doses: dict[int, int] = {}
        for item in itens:
            if item["tipo"] == "dose":
                demand_doses[item["produto_id"]] = demand_doses.get(item["produto_id"], 0) + item["quantidade"]
        for pid, qtd_doses in demand_doses.items():
            p = cur.execute("SELECT nome,quantidade,doses_por_garrafa,volume_garrafa_ml,is_garrafa,ativo FROM produtos WHERE id=?", (pid,)).fetchone()
            if not p or not p["ativo"] or not p["is_garrafa"]:
                raise ValueError("Um produto vendido por dose não está configurado corretamente.")
            abertas = cur.execute("SELECT COALESCE(SUM(doses_restantes),0) AS q FROM garrafas_abertas WHERE produto_id=? AND status='aberta' AND doses_restantes>0", (pid,)).fetchone()["q"]
            rendimento = float(p["doses_por_garrafa"] or 0)
            if rendimento <= 0:
                from domain.bottle_rules import calcular_doses_estimadas
                _, rendimento = calcular_doses_estimadas(int(p["volume_garrafa_ml"] or 900), 150, 0.05)
            deficit = max(0.0, qtd_doses - float(abertas or 0))
            necessarias = math.ceil(max(0.0, deficit-1e-9) / rendimento) if deficit > 0 else 0
            if necessarias and pid not in autorizadas:
                raise ValueError(f"É necessário confirmar a abertura de {necessarias} garrafa(s) de '{p['nome']}' antes de concluir a venda.")
            if necessarias > int(p["quantidade"]):
                raise ValueError(f"Não há garrafas fechadas suficientes para '{p['nome']}'. Necessárias: {necessarias}; disponíveis: {p['quantidade']}.")

        # Baixa de doses em FIFO real; toda garrafa nova precisa estar autorizada.
        for item in itens:
            if item["tipo"] != "dose":
                continue
            restante = float(item["quantidade"])
            pid = item["produto_id"]
            while restante > 1e-8:
                bottle = cur.execute("""SELECT id,doses_restantes FROM garrafas_abertas
                    WHERE produto_id=? AND status='aberta' AND doses_restantes>0
                    ORDER BY substr(data_abertura,7,4)||substr(data_abertura,4,2)||substr(data_abertura,1,2)||substr(data_abertura,12,8) ASC, id ASC LIMIT 1""", (pid,)).fetchone()
                if bottle:
                    consumida = min(restante, float(bottle["doses_restantes"]))
                    novo_saldo = max(0.0, float(bottle["doses_restantes"]) - consumida)
                    estado = "fechada" if novo_saldo <= 1e-8 else "aberta"
                    fechado_em = agora if estado == "fechada" else None
                    cur.execute("UPDATE garrafas_abertas SET doses_restantes=?,status=?,data_fechamento=? WHERE id=? AND status='aberta'", (novo_saldo,estado,fechado_em,bottle["id"]))
                    cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)", (pid,"consumo_dose",consumida,agora,item["produto"]["nome"]))
                    restante -= consumida
                else:
                    opened = _abrir_garrafa_na_transacao(cur, pid)
                    # O operador autorizou antecipadamente a quantidade exibida no diálogo.

        # Baixa itens por unidade, com controle de concorrência/estoque agregado.
        unidade_qtd: dict[int, int] = {}
        for item in itens:
            if item["tipo"] == "unidade":
                unidade_qtd[item["produto_id"]] = unidade_qtd.get(item["produto_id"], 0) + item["quantidade"]
        for pid, qtd in unidade_qtd.items():
            p = cur.execute("SELECT nome,quantidade FROM produtos WHERE id=? AND ativo=1", (pid,)).fetchone()
            if not p or int(p["quantidade"]) < qtd:
                nome = p["nome"] if p else str(pid)
                raise ValueError(f"Estoque insuficiente para '{nome}'. Disponível: {p['quantidade'] if p else 0}.")
            cur.execute("UPDATE produtos SET quantidade=quantidade-? WHERE id=? AND quantidade>=?", (qtd,pid,qtd))
            if cur.rowcount != 1:
                raise ValueError(f"O estoque de '{p['nome']}' mudou. Atualize e tente novamente.")
            cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)", (pid,"saida_venda",qtd,agora,p["nome"]))

        cur.execute("""INSERT INTO vendas(dia_operacao_id,data,status,forma_pagamento,desconto_percentual,
            desconto_valor,total_bruto,total_liquido,lucro_total,observacao,cliente_nome)
            VALUES(?,?,?,?,?,?,?,?,0,?,?)""",
            (dia_operacao_id,agora,status,forma_final,float(pct_geral),float(Decimal(desconto_geral_cents)*CENTAVO),
             float(Decimal(total_bruto_cents)*CENTAVO),float(total_final),observacao,cliente_nome))
        venda_id = int(cur.lastrowid)

        lucro_total_cents = 0
        for item in itens:
            p = item["produto"]
            if item["tipo"] == "dose":
                rendimento = float(p["doses_por_garrafa"] or 0)
                if rendimento <= 0:
                    from domain.bottle_rules import calcular_doses_estimadas
                    _, rendimento = calcular_doses_estimadas(int(p["volume_garrafa_ml"] or 900),150,0.05)
                rendimento_custeavel = max(1e-9, rendimento)
                custo_unit = _dinheiro(Decimal(str(p["preco_custo"] or 0)) / Decimal(str(rendimento_custeavel)))
            else:
                custo_unit = _dinheiro(p["preco_custo"] or 0)
            custo_total_cents = _centavos(custo_unit * item["quantidade"])
            lucro_item_cents = item["liquido_cents"] - custo_total_cents
            lucro_total_cents += lucro_item_cents
            cur.execute("""INSERT INTO venda_itens(venda_id,produto_id,nome_produto,quantidade,preco_unitario,
                preco_custo,desconto_percentual,desconto_valor,subtotal_bruto,subtotal,lucro_item,tipo,desconto_geral_rateado)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (venda_id,item["produto_id"],item["nome"],item["quantidade"],float(item["preco"]),float(custo_unit),
                 float(item["desconto_percentual"]),float(Decimal(item["desconto_item_cents"])*CENTAVO),
                 float(Decimal(item["bruto_cents"])*CENTAVO),float(Decimal(item["liquido_cents"])*CENTAVO),
                 float(Decimal(lucro_item_cents)*CENTAVO),item["tipo"],float(Decimal(item["desconto_geral_rateado_cents"])*CENTAVO)))
        cur.execute("UPDATE vendas SET lucro_total=? WHERE id=?", (float(Decimal(lucro_total_cents)*CENTAVO),venda_id))

        for pag in pagamentos_registrados:
            cur.execute("INSERT INTO venda_pagamentos(venda_id,forma_pagamento,valor,data,dia_operacao_id) VALUES(?,?,?,?,?)",
                        (venda_id,pag["forma_pagamento"],float(pag["valor"]),agora,dia_operacao_id))
        cur.execute("INSERT INTO auditoria(acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",
                    ("venda_registrada",f"Venda #{venda_id} registrada como {status}; total R$ {total_final:.2f}",1,agora,f"Venda #{venda_id}"))
        return venda_id


def listar_vendas(status=None, data_inicio=None, data_fim=None, dia_operacao_id=None,
                 limite: Optional[int] = None, offset: int = 0,
                 venda_id: Optional[int] = None) -> List[Dict]:
    """Lista vendas com itens/pagamentos carregados em lote (sem consultas N+1)."""
    if limite is not None:
        try:
            limite = int(limite)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("O limite de vendas deve ser um inteiro positivo.") from exc
        if limite <= 0:
            raise ValueError("O limite de vendas deve ser um inteiro positivo.")
        limite = min(limite, 5000)
    try:
        offset = int(offset)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("O deslocamento da página deve ser um inteiro não negativo.") from exc
    if offset < 0:
        raise ValueError("O deslocamento da página não pode ser negativo.")

    with get_db() as (_, cur):
        query = "SELECT * FROM vendas WHERE status <> 'cancelado'"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if venda_id is not None:
            try:
                venda_id = int(venda_id)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Identificador da venda inválido.") from exc
            if venda_id <= 0:
                raise ValueError("Identificador da venda deve ser positivo.")
            query += " AND id = ?"
            params.append(venda_id)
        if dia_operacao_id is not None:
            query += " AND dia_operacao_id = ?"
            params.append(dia_operacao_id)
        else:
            date_expr = "substr(data,7,4)||substr(data,4,2)||substr(data,1,2)"
            if data_inicio:
                query += f" AND {date_expr} >= ?"
                params.append(_data_key(data_inicio))
            if data_fim:
                query += f" AND {date_expr} <= ?"
                params.append(_data_key(data_fim))
        query += f" ORDER BY {_sort_data_sql('data')} DESC, id DESC"
        if limite is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend((limite, offset))
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        vendas = [dict(row) for row in cur.execute(query, params).fetchall()]
        if not vendas:
            return []

        itens_por_venda: dict[int, list[dict]] = {}
        pagamentos_por_venda: dict[int, list[dict]] = {}
        ids = [int(venda["id"]) for venda in vendas]
        for inicio in range(0, len(ids), 400):
            lote = ids[inicio:inicio + 400]
            placeholders = ",".join("?" for _ in lote)
            rows_itens = cur.execute(
                f"SELECT vi.*, p.codigo_barras FROM venda_itens vi "
                f"LEFT JOIN produtos p ON vi.produto_id=p.id "
                f"WHERE vi.venda_id IN ({placeholders}) ORDER BY vi.venda_id, vi.id",
                lote,
            ).fetchall()
            for row in rows_itens:
                item = dict(row)
                itens_por_venda.setdefault(int(item["venda_id"]), []).append(item)

            rows_pagamentos = cur.execute(
                f"SELECT venda_id, forma_pagamento, valor, data FROM venda_pagamentos "
                f"WHERE venda_id IN ({placeholders}) ORDER BY venda_id, id",
                lote,
            ).fetchall()
            for row in rows_pagamentos:
                pagamento = dict(row)
                pagamentos_por_venda.setdefault(int(pagamento["venda_id"]), []).append(pagamento)

        for venda in vendas:
            venda_id = int(venda["id"])
            venda["itens"] = itens_por_venda.get(venda_id, [])
            venda["pagamentos"] = pagamentos_por_venda.get(venda_id, [])
        return vendas


def obter_total_fiado_aberto() -> float:
    """Retorna o saldo total de fiado sem materializar itens/pagamentos das vendas."""
    with get_db() as (_, cur):
        row = cur.execute(
            "SELECT COALESCE(SUM(total_liquido), 0) FROM vendas WHERE status='pendente'"
        ).fetchone()
        return float(row[0] or 0.0)


def contar_vendas(status=None, data_inicio=None, data_fim=None, dia_operacao_id=None) -> int:
    """Conta todas as vendas que correspondem aos filtros, sem limite visual."""
    with get_db() as (_, cur):
        query = "SELECT COUNT(*) FROM vendas WHERE status <> 'cancelado'"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if dia_operacao_id is not None:
            query += " AND dia_operacao_id = ?"
            params.append(dia_operacao_id)
        else:
            date_expr = "substr(data,7,4)||substr(data,4,2)||substr(data,1,2)"
            if data_inicio:
                query += f" AND {date_expr} >= ?"
                params.append(_data_key(data_inicio))
            if data_fim:
                query += f" AND {date_expr} <= ?"
                params.append(_data_key(data_fim))
        return int(cur.execute(query, params).fetchone()[0])


def atualizar_status_venda(venda_id: int, novo_status: str, pagamentos: Optional[List[Dict[str, Any]]] = None):
    """Quita um fiado somente quando os pagamentos fecham o total exato."""
    if novo_status != "finalizado":
        raise ValueError("Transição de status não permitida por esta operação.")
    agora=_data_agora()
    with get_db() as (conn,cur):
        conn.execute("BEGIN IMMEDIATE")
        venda=cur.execute("SELECT * FROM vendas WHERE id=?",(venda_id,)).fetchone()
        if not venda: raise ValueError("Venda não encontrada.")
        if venda['status'] == 'finalizado': return
        if venda['status'] != 'pendente': raise ValueError("Somente vendas fiadas pendentes podem ser quitadas.")
        dia = cur.execute("SELECT id FROM dias_operacao WHERE status='aberto' ORDER BY id DESC LIMIT 1").fetchone()
        if not dia:
            raise ValueError("Abra um dia de operação antes de registrar o recebimento do fiado.")
        dia_recebimento_id = int(dia['id'])
        total=_dinheiro(venda['total_liquido'])
        pags=_validar_pagamentos(pagamentos,total,"Dinheiro")
        for pag in pags:
            cur.execute("INSERT INTO venda_pagamentos(venda_id,forma_pagamento,valor,data,dia_operacao_id) VALUES(?,?,?,?,?)",(venda_id,pag['forma_pagamento'],float(pag['valor']),agora,dia_recebimento_id))
        cur.execute("UPDATE vendas SET status='finalizado' WHERE id=? AND status='pendente'",(venda_id,))
        if cur.rowcount != 1: raise ValueError("O status da venda mudou durante a operação.")
        cur.execute("INSERT INTO auditoria(acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",("fiado_quitado",f"Venda #{venda_id} quitada; total recebido R$ {total:.2f}",1,agora,f"Venda #{venda_id}"))


def _historico_unificado_sql() -> str:
    """Fonte unificada, mantendo identificador/origem para ordenação estável."""
    return (
        "SELECT id AS registro_id, 'historico' AS origem, nome_produto AS nome, "
        "tipo, quantidade, data FROM historico "
        "UNION ALL "
        "SELECT id AS registro_id, 'auditoria' AS origem, nome_produto AS nome, "
        "acao AS tipo, quantidade, data FROM auditoria"
    )


def _filtro_historico(data: Optional[str]):
    if data:
        _data_key(data)
        return "WHERE data LIKE ?", [f"{data}%"]
    return "", []


def buscar_historico_completo(
    data: Optional[str] = None, limite: int = 200, offset: int = 0,
) -> List[Dict]:
    """Lista movimentações por página; os registros fora da página continuam no banco."""
    try:
        limite, offset = int(limite), int(offset)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Limite e deslocamento da paginação devem ser inteiros.") from exc
    if limite <= 0:
        raise ValueError("O limite da página deve ser positivo.")
    if offset < 0:
        raise ValueError("O deslocamento da página não pode ser negativo.")
    limite = min(limite, 500)
    base = _historico_unificado_sql()
    where, params = _filtro_historico(data)
    with get_db() as (_, cur):
        cur.execute(
            f"SELECT * FROM ({base}) AS historico_unificado {where} "
            f"ORDER BY {_sort_data_sql('data')} DESC, registro_id DESC, origem ASC "
            "LIMIT ? OFFSET ?",
            (*params, limite, offset),
        )
        return [dict(r) for r in cur.fetchall()]


def contar_historico_completo(data: Optional[str] = None) -> int:
    """Conta o total de movimentações, sem o limite de exibição da interface."""
    base = _historico_unificado_sql()
    where, params = _filtro_historico(data)
    with get_db() as (_, cur):
        row = cur.execute(
            f"SELECT COUNT(*) FROM ({base}) AS historico_unificado {where}", params,
        ).fetchone()
        return int(row[0])