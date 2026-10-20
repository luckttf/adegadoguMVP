"""Persistência de dias de operação."""
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
from infrastructure.database.connection import get_db

def abrir_dia() -> Tuple[Optional[int], bool]:
    with get_db() as (conn,cur):
        cur.execute("BEGIN IMMEDIATE")
        row=cur.execute("SELECT id FROM dias_operacao WHERE status='aberto' LIMIT 1").fetchone()
        if row: return None,False
        agora=datetime.now()
        cur.execute("INSERT INTO dias_operacao(data_abertura,horario_abertura,status) VALUES(?,?,'aberto')",(agora.strftime('%d/%m/%Y'),agora.strftime('%H:%M:%S')))
        return cur.lastrowid,True

def fechar_dia(dia_id: int):
    """Fecha um dia e persiste um retrato financeiro imutável do momento do fechamento."""
    with get_db() as (conn, cur):
        conn.execute("BEGIN IMMEDIATE")
        dia = cur.execute("SELECT id FROM dias_operacao WHERE id=? AND status='aberto'", (dia_id,)).fetchone()
        if not dia:
            raise ValueError("Dia não existe ou já foi fechado.")
        agora = datetime.now()
        vendido = cur.execute("""SELECT COALESCE(SUM(total_liquido),0) AS total,
                    COALESCE(SUM(lucro_total),0) AS lucro, COUNT(*) AS quantidade
            FROM vendas WHERE dia_operacao_id=? AND status <> 'cancelado'""", (dia_id,)).fetchone()
        desconto_header = cur.execute("""SELECT COALESCE(SUM(desconto_valor),0) FROM vendas
            WHERE dia_operacao_id=? AND status <> 'cancelado'""", (dia_id,)).fetchone()[0]
        desconto_itens = cur.execute("""SELECT COALESCE(SUM(vi.desconto_valor),0)
            FROM venda_itens vi JOIN vendas v ON v.id=vi.venda_id
            WHERE v.dia_operacao_id=? AND v.status <> 'cancelado'""", (dia_id,)).fetchone()[0]
        recebido = cur.execute("SELECT COALESCE(SUM(valor),0) FROM venda_pagamentos WHERE dia_operacao_id=?", (dia_id,)).fetchone()[0]
        # Mostra todo o saldo de fiado da loja no instante do fechamento, inclusive de dias anteriores.
        fiado = cur.execute("SELECT COALESCE(SUM(total_liquido),0) FROM vendas WHERE status='pendente'").fetchone()[0]
        cur.execute("""UPDATE dias_operacao SET status='fechado',data_fechamento=?,horario_fechamento=?,
            total_vendido_fechamento=?,total_recebido_fechamento=?,fiado_aberto_fechamento=?,
            total_descontos_fechamento=?,lucro_estimado_fechamento=?,quantidade_vendas_fechamento=?
            WHERE id=? AND status='aberto'""",
            (agora.strftime('%d/%m/%Y'), agora.strftime('%H:%M:%S'), float(vendido['total']),
             float(recebido), float(fiado), float(desconto_header or 0)+float(desconto_itens or 0),
             float(vendido['lucro']), int(vendido['quantidade']), dia_id))
        if cur.rowcount != 1:
            raise ValueError("O dia mudou de estado durante o fechamento. Atualize a tela e tente novamente.")

def obter_dia_aberto() -> Optional[Dict[str, Any]]:
    with get_db() as (_,cur):
        row=cur.execute("SELECT * FROM dias_operacao WHERE status='aberto' ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

def obter_resumo_dia_operacao(dia_id: Optional[int] = None) -> Tuple[Optional[Dict], List[Dict]]:
    with get_db() as (conn,cur):
        if dia_id is None:
            dia=cur.execute("SELECT * FROM dias_operacao WHERE status='aberto' ORDER BY id DESC LIMIT 1").fetchone()
        else:
            dia=cur.execute("SELECT * FROM dias_operacao WHERE id=?",(dia_id,)).fetchone()
        if not dia: return None,[]
        cur.execute("""SELECT v.status,
                   CASE WHEN v.status='pendente' THEN 'Fiado' ELSE COALESCE(v.forma_pagamento,'Não informado') END AS forma_pagamento,
                   COUNT(*) AS qtd_vendas, SUM(v.total_bruto) AS total_bruto,
                   SUM(v.desconto_valor + COALESCE(i.desconto_itens,0)) AS total_desconto,
                   SUM(v.total_liquido) AS total_liquido, SUM(v.lucro_total) AS lucro_total
            FROM vendas v LEFT JOIN (SELECT venda_id,SUM(desconto_valor) AS desconto_itens FROM venda_itens GROUP BY venda_id) i ON i.venda_id=v.id
            WHERE v.dia_operacao_id=? AND v.status <> 'cancelado'
            GROUP BY v.status, forma_pagamento ORDER BY v.status, forma_pagamento""",(dia['id'],))
        return dict(dia),[dict(r) for r in cur.fetchall()]



def listar_dias_operacao(limite: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retorna uma fatia dos dias, sem remover ou ocultar registros do banco.

    ``offset`` habilita paginação na interface; o limite é apenas visual e não
    representa retenção histórica.
    """
    try:
        limite = int(limite)
        offset = int(offset)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Limite e deslocamento da paginação devem ser inteiros.") from exc
    if limite <= 0:
        raise ValueError("O limite da página deve ser positivo.")
    if offset < 0:
        raise ValueError("O deslocamento da página não pode ser negativo.")
    limite = min(limite, 500)
    with get_db() as (_, cur):
        rows = cur.execute(
            "SELECT * FROM dias_operacao ORDER BY id DESC LIMIT ? OFFSET ?",
            (limite, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def contar_dias_operacao() -> int:
    """Conta todos os dias registrados, incluindo dias antigos e fechados."""
    with get_db() as (_, cur):
        return int(cur.execute("SELECT COUNT(*) FROM dias_operacao").fetchone()[0])


def obter_resumo_pagamentos_dia(dia_id: int) -> List[Dict[str, Any]]:
    """Valores recebidos efetivamente, discriminados pelo meio de pagamento."""
    with get_db() as (_, cur):
        rows = cur.execute("""SELECT vp.forma_pagamento, SUM(vp.valor) AS total_liquido,
                   COUNT(DISTINCT vp.venda_id) AS qtd_vendas, 'finalizado' AS status
            FROM venda_pagamentos vp
            JOIN vendas v ON v.id = vp.venda_id
            WHERE vp.dia_operacao_id = ?
            GROUP BY vp.forma_pagamento ORDER BY vp.forma_pagamento""", (dia_id,)).fetchall()
        return [dict(r) for r in rows]
