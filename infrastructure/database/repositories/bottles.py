"""Ciclo de vida auditável das garrafas abertas."""
import math
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from infrastructure.database.connection import get_db, conectar
from domain.bottle_rules import calcular_doses_estimadas


def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _abrir_garrafa_na_transacao(cur, produto_id: int) -> dict[str, Any]:
    produto = cur.execute("SELECT id,nome,quantidade,doses_por_garrafa,volume_garrafa_ml,is_garrafa,ativo FROM produtos WHERE id=?", (produto_id,)).fetchone()
    if not produto or not produto['ativo']:
        raise ValueError("Garrafa não encontrada ou produto arquivado.")
    if not produto['is_garrafa']:
        raise ValueError(f"'{produto['nome']}' não está cadastrado como produto vendido por dose.")
    if produto['quantidade'] <= 0:
        raise ValueError(f"Estoque insuficiente de garrafas fechadas para '{produto['nome']}'.")
    doses = float(produto['doses_por_garrafa'] or 0)
    if doses <= 0:
        _, doses = calcular_doses_estimadas(int(produto['volume_garrafa_ml'] or 900), 150, 0.05)
    if not math.isfinite(doses) or doses <= 0:
        raise ValueError(f"Rendimento configurado inválido para '{produto['nome']}'.")
    updated = cur.execute("UPDATE produtos SET quantidade=quantidade-1 WHERE id=? AND quantidade>0 AND ativo=1", (produto_id,))
    if updated.rowcount != 1:
        raise ValueError(f"Estoque de garrafas fechadas insuficiente para '{produto['nome']}'.")
    stamp = _agora()
    cur.execute("""INSERT INTO garrafas_abertas
        (produto_id,data_abertura,doses_restantes,perdas_doses,status,doses_iniciais,data_fechamento)
        VALUES(?,?,?,0,'aberta',?,NULL)""", (produto_id,stamp,doses,doses))
    bottle_id = cur.lastrowid
    cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",
                (produto_id,'abertura',1,stamp,produto['nome']))
    cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                (produto_id,'garrafa_aberta',f"Garrafa #{bottle_id} aberta; rendimento inicial {doses:.2f} doses",1,stamp,produto['nome']))
    return {"id": bottle_id, "produto_id": produto_id, "nome": produto['nome'], "doses_iniciais": doses}


def abrir_garrafa(produto_id: int, conn_externa: sqlite3.Connection | None = None) -> tuple[bool, str, int]:
    owns = conn_externa is None
    conn = conn_externa if conn_externa is not None else conectar()
    try:
        if owns: conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        info = _abrir_garrafa_na_transacao(cur, produto_id)
        if owns: conn.commit()
        return True, f"Garrafa de '{info['nome']}' aberta. {info['doses_iniciais']:.1f} doses estimadas.", info['id']
    except Exception as exc:
        if owns: conn.rollback()
        if isinstance(exc, (ValueError, sqlite3.Error)):
            return False, str(exc), 0
        raise
    finally:
        if owns: conn.close()


def prever_abertura_garrafas(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pré-calcula garrafas que exigirão confirmação; não altera estoque."""
    demandas: dict[int, float] = {}
    nomes: dict[int, str] = {}
    for item in itens:
        if item.get('tipo') != 'dose': continue
        pid = int(item['produto_id'])
        qtd = float(item['quantidade'])
        if not math.isfinite(qtd) or qtd <= 0: raise ValueError("A quantidade de doses deve ser positiva.")
        demandas[pid] = demandas.get(pid, 0.0) + qtd
        nomes[pid] = str(item.get('nome', pid))
    out = []
    with get_db() as (_, cur):
        for pid, needed in demandas.items():
            p=cur.execute("SELECT nome,quantidade,doses_por_garrafa,volume_garrafa_ml,is_garrafa,ativo FROM produtos WHERE id=?",(pid,)).fetchone()
            if not p or not p['ativo'] or not p['is_garrafa']:
                raise ValueError(f"Produto {nomes[pid]} não está ativo como garrafa vendida por dose.")
            opened=cur.execute("SELECT COALESCE(SUM(doses_restantes),0) AS q FROM garrafas_abertas WHERE produto_id=? AND status='aberta' AND doses_restantes>0",(pid,)).fetchone()['q']
            yield_q=float(p['doses_por_garrafa'] or 0)
            if yield_q <= 0: _, yield_q=calcular_doses_estimadas(int(p['volume_garrafa_ml'] or 900),150,0.05)
            deficit=max(0.0,needed-float(opened))
            bottles=int(math.ceil(max(0.0, deficit-1e-9)/yield_q)) if deficit>0 else 0
            out.append({"produto_id":pid,"nome":p['nome'],"doses_vendidas":needed,"doses_abertas":float(opened),
                        "doses_por_garrafa":yield_q,"garrafas_necessarias":bottles,
                        "garrafas_disponiveis":int(p['quantidade']),"suficiente":int(p['quantidade'])>=bottles})
    return out


def fechar_garrafa(garrafa_aberta_id: int) -> tuple[bool, str]:
    with get_db() as (conn,cur):
        g=cur.execute("SELECT ga.*,p.nome FROM garrafas_abertas ga JOIN produtos p ON p.id=ga.produto_id WHERE ga.id=?",(garrafa_aberta_id,)).fetchone()
        if not g: return False,"Garrafa aberta não encontrada."
        if g['status'] != 'aberta': return False,"Esta garrafa já foi encerrada e não pode ser reaberta."
        remaining=max(0.0,float(g['doses_restantes']))
        stamp=_agora()
        cur.execute("UPDATE garrafas_abertas SET doses_restantes=0,status='fechada',data_fechamento=? WHERE id=? AND status='aberta'",(stamp,garrafa_aberta_id))
        if cur.rowcount != 1: return False,"O estado da garrafa mudou; atualize a tela."
        if remaining > 0:
            cur.execute("UPDATE garrafas_abertas SET perdas_doses=perdas_doses+? WHERE id=?",(remaining,garrafa_aberta_id))
            cur.execute("INSERT INTO perdas_registro(garrafa_aberta_id,produto_id,quantidade,motivo,data) VALUES(?,?,?,?,?)",
                        (garrafa_aberta_id,g['produto_id'],remaining,"Sobra descartada ao encerrar garrafa",stamp))
        cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",(g['produto_id'],'fechamento',remaining,stamp,g['nome']))
        cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                    (g['produto_id'],'garrafa_fechada',f"Garrafa #{garrafa_aberta_id} encerrada; sobra descartada: {remaining:.2f} dose(s)",remaining,stamp,g['nome']))
    return True, f"Garrafa encerrada. Sobra registrada como perda: {remaining:.2f} dose(s)."


def ajustar_doses_restantes(garrafa_aberta_id: int, novas_doses: float) -> tuple[bool, str]:
    try: novas_doses=float(novas_doses)
    except (TypeError,ValueError): return False,"Quantidade de doses inválida."
    if not math.isfinite(novas_doses) or novas_doses < 0: return False,"A quantidade não pode ser negativa ou inválida."
    with get_db() as (conn,cur):
        g=cur.execute("SELECT ga.*,p.nome FROM garrafas_abertas ga JOIN produtos p ON p.id=ga.produto_id WHERE ga.id=?",(garrafa_aberta_id,)).fetchone()
        if not g: return False,"Garrafa não encontrada."
        if g['status'] != 'aberta': return False,"Garrafa encerrada não pode ser reativada."
        capacidade=float(g['doses_iniciais'] or 0)
        if novas_doses > capacidade + 1e-8: return False,f"O ajuste não pode exceder o rendimento inicial ({capacidade:.2f})."
        anterior=float(g['doses_restantes']); stamp=_agora()
        estado='fechada' if novas_doses == 0 else 'aberta'
        closed_at=stamp if novas_doses == 0 else None
        cur.execute("UPDATE garrafas_abertas SET doses_restantes=?,status=?,data_fechamento=? WHERE id=? AND status='aberta'",(novas_doses,estado,closed_at,garrafa_aberta_id))
        if cur.rowcount != 1: return False,"O estado da garrafa mudou; atualize a lista."
        cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                    (g['produto_id'],'ajuste_doses',f"Garrafa #{garrafa_aberta_id}: saldo alterado de {anterior:.2f} para {novas_doses:.2f}; motivo não informado",novas_doses-anterior,stamp,g['nome']))
    return True,"Saldo de doses ajustado e auditado."


def registrar_perda_dose(garrafa_aberta_id: int, quantidade: float, motivo: str = "Perda/descarte") -> tuple[bool, str]:
    try: quantidade=float(quantidade)
    except (TypeError,ValueError): return False,"Quantidade de perda inválida."
    if not math.isfinite(quantidade) or quantidade <= 0: return False,"A quantidade de perda deve ser positiva."
    motivo=(motivo or "Perda/descarte").strip() or "Perda/descarte"
    with get_db() as (conn,cur):
        g=cur.execute("SELECT ga.*,p.nome FROM garrafas_abertas ga JOIN produtos p ON p.id=ga.produto_id WHERE ga.id=?",(garrafa_aberta_id,)).fetchone()
        if not g: return False,"Garrafa não encontrada."
        if g['status'] != 'aberta': return False,"Não é possível registrar perda em uma garrafa encerrada."
        if quantidade > float(g['doses_restantes'])+1e-8: return False,f"Perda maior que o saldo disponível ({g['doses_restantes']:.2f})."
        restantes=max(0.0,float(g['doses_restantes'])-quantidade); stamp=_agora()
        estado='fechada' if restantes <= 1e-8 else 'aberta'; fechada_em=stamp if estado=='fechada' else None
        cur.execute("UPDATE garrafas_abertas SET doses_restantes=?,perdas_doses=perdas_doses+?,status=?,data_fechamento=? WHERE id=? AND status='aberta'",
                    (restantes,quantidade,estado,fechada_em,garrafa_aberta_id))
        if cur.rowcount != 1: return False,"O estado da garrafa mudou; atualize a lista."
        cur.execute("INSERT INTO perdas_registro(garrafa_aberta_id,produto_id,quantidade,motivo,data) VALUES(?,?,?,?,?)",
                    (garrafa_aberta_id,g['produto_id'],quantidade,motivo,stamp))
        cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",(g['produto_id'],'perda_dose',quantidade,stamp,g['nome']))
        cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                    (g['produto_id'],'perda_dose',f"Garrafa #{garrafa_aberta_id}: {quantidade:.2f} dose(s). Motivo: {motivo}",quantidade,stamp,g['nome']))
    return True,"Perda de dose registrada e auditada."


def obter_perdas_por_produto(produto_id: int | None = None, limite: int = 100) -> list[dict]:
    limite=max(1,min(int(limite),1000))
    with get_db() as (_,cur):
        if produto_id:
            rows=cur.execute("SELECT pr.*,p.nome AS nome_produto FROM perdas_registro pr LEFT JOIN produtos p ON p.id=pr.produto_id WHERE pr.produto_id=? ORDER BY pr.id DESC LIMIT ?",(produto_id,limite)).fetchall()
        else:
            rows=cur.execute("SELECT pr.*,p.nome AS nome_produto FROM perdas_registro pr LEFT JOIN produtos p ON p.id=pr.produto_id ORDER BY pr.id DESC LIMIT ?",(limite,)).fetchall()
        return [dict(r) for r in rows]


def obter_doses_disponiveis(produto_id: int) -> float:
    with get_db() as (_,cur):
        row=cur.execute("SELECT COALESCE(SUM(doses_restantes),0) AS q FROM garrafas_abertas WHERE produto_id=? AND status='aberta' AND doses_restantes>0",(produto_id,)).fetchone()
        return float(row['q'] or 0)


def obter_doses_disponiveis_por_produto() -> dict[int, float]:
    """Retorna os saldos de doses de todos os produtos em uma única consulta."""
    with get_db() as (_, cur):
        rows = cur.execute("""SELECT produto_id, COALESCE(SUM(doses_restantes), 0) AS quantidade
            FROM garrafas_abertas
            WHERE status='aberta' AND doses_restantes > 0
            GROUP BY produto_id""").fetchall()
        return {int(row["produto_id"]): float(row["quantidade"] or 0) for row in rows}


def obter_garrafas_abertas(produto_id: int | None = None) -> list[dict]:
    with get_db() as (_,cur):
        where="WHERE ga.status='aberta' AND ga.doses_restantes>0"; params=[]
        if produto_id is not None: where += " AND ga.produto_id=?"; params.append(produto_id)
        # Data legada dd/mm/yyyy não é cronologicamente ordenável como texto.
        rows=cur.execute(f"SELECT ga.*,p.nome AS nome_produto FROM garrafas_abertas ga JOIN produtos p ON p.id=ga.produto_id {where} ORDER BY substr(ga.data_abertura,7,4)||substr(ga.data_abertura,4,2)||substr(ga.data_abertura,1,2)||substr(ga.data_abertura,12,8) ASC",params).fetchall()
        return [dict(r) for r in rows]
