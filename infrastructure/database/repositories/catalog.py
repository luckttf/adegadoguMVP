"""Persistência de categorias, catálogo e movimentações unitárias."""
import sqlite3, csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from infrastructure.database.connection import get_db
from domain.bottle_rules import VOLUME_GARRAFA_ML_PADRAO


class QuantidadeInteiroInvalido(ValueError):
    """Erro de validação para campos que devem representar unidades inteiras."""


def _inteiro_exato(valor, campo: str) -> int:
    """Converte apenas números inteiros exatos; nunca trunca 2.7 para 2."""
    try:
        numero = Decimal(str(valor).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        raise QuantidadeInteiroInvalido(f"{campo} deve ser um número inteiro válido.")
    if not numero.is_finite() or numero != numero.to_integral_value():
        raise QuantidadeInteiroInvalido(f"{campo} deve ser um número inteiro, sem frações.")
    return int(numero)


def obter_todas_categorias() -> list[tuple[int, str]]:
    with get_db() as (_, cur):
        cur.execute("SELECT id, nome FROM categorias ORDER BY nome")
        return [(row["id"], row["nome"]) for row in cur.fetchall()]

def obter_categorias_unicas() -> list[str]:
    return [nome for _, nome in obter_todas_categorias()]

def adicionar_categoria(nome: str) -> tuple[bool, str]:
    try:
        with get_db() as (conn, cur):
            conn.execute("INSERT INTO categorias (nome) VALUES (?)", (nome,))
        return True, "Categoria criada."
    except sqlite3.IntegrityError:
        return False, "Categoria já existe."

def remover_categoria(cat_id: int) -> tuple[bool, str]:
    with get_db() as (conn, cur):
        cur.execute("SELECT COUNT(*) FROM produtos WHERE categoria_id = ?", (cat_id,))
        if cur.fetchone()[0] > 0:
            return False, "Existem produtos com essa categoria."
        cur.execute("DELETE FROM categorias WHERE id = ?", (cat_id,))
        return True, "Categoria removida."

def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if "categoria_nome" in d:
        d["categoria"] = d.pop("categoria_nome")
    d["is_garrafa"] = bool(d.get("is_garrafa", 0))
    return d

def buscar_produtos(termo: str = "", limite: int | None = None) -> list[dict[str, Any]]:
    """Pesquisa produtos; `limite` permite consultas baratas para autocomplete."""
    termo = (termo or "").strip()
    params = []
    where = "WHERE p.ativo = 1"
    if termo:
        where += " AND (unaccent(p.nome) LIKE unaccent(?) OR unaccent(COALESCE(c.nome,'')) LIKE unaccent(?) OR p.codigo_barras LIKE ?)"
        params.extend((f"%{termo}%", f"%{termo}%", f"%{termo}%"))
    order_by = "ORDER BY c.nome, p.nome"
    if termo:
        order_by = "ORDER BY CASE WHEN unaccent(p.nome) = unaccent(?) THEN 0 ELSE 1 END, c.nome, p.nome"
        params.append(termo)
    query = f"SELECT p.*, c.nome AS categoria_nome FROM produtos p LEFT JOIN categorias c ON p.categoria_id = c.id {where} {order_by}"
    if limite is not None:
        try:
            limite = max(1, min(int(limite), 500))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("O limite de produtos deve ser um inteiro positivo.")
        query += " LIMIT ?"
        params.append(limite)
    with get_db() as (_, cur):
        cur.execute(query, params)
        return [_row_to_dict(r) for r in cur.fetchall()]

def buscar_produto_por_codigo_barras(codigo: str) -> dict[str, Any] | None:
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    with get_db() as (_, cur):
        cur.execute("SELECT * FROM produtos WHERE codigo_barras = ? AND ativo = 1", (codigo,))
        produto = cur.fetchone()
        return _row_to_dict(produto) if produto else None


# [CORREÇÃO] Função interna que assume que o cursor já está em uma transação.
# Usada por adicionar_produto e importar_csv para evitar conexões duplicadas.
def _inserir_produto_cur(cur, nome, categoria_nome, quantidade, preco, codigo_barras,
                          estoque_minimo, estoque_medio, preco_custo, is_garrafa,
                          doses_por_garrafa, preco_dose, volume_garrafa_ml):
    if codigo_barras:
        dup = cur.execute("SELECT nome FROM produtos WHERE codigo_barras = ? AND ativo = 1", (codigo_barras,)).fetchone()
        if dup:
            raise ValueError(f"Código de barras já cadastrado em '{dup['nome']}'.")
    
    cat_id = None
    if categoria_nome:
        row = cur.execute("SELECT id FROM categorias WHERE nome = ?", (categoria_nome,)).fetchone()
        if row:
            cat_id = row['id']
        else:
            cur.execute("INSERT INTO categorias(nome) VALUES (?)", (categoria_nome,))
            cat_id = cur.lastrowid
            
    cur.execute("""INSERT INTO produtos
        (nome,categoria_id,quantidade,preco,codigo_barras,estoque_minimo,estoque_medio,
         preco_custo,is_garrafa,doses_por_garrafa,preco_dose,volume_garrafa_ml,ativo)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)""",
        (nome,cat_id,quantidade,preco,codigo_barras,estoque_minimo,estoque_medio,
         preco_custo,1 if is_garrafa else 0,doses_por_garrafa,preco_dose,volume_garrafa_ml))
    
    produto_id = cur.lastrowid
    if quantidade:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",
                    (produto_id,'estoque_inicial',quantidade,agora,nome))
    return produto_id


def adicionar_produto(nome: str, categoria_nome: str, quantidade: int, preco: float,
                      codigo_barras: str | None = None, estoque_minimo: int = 5,
                      estoque_medio: int = 15, preco_custo: float = 0.0,
                      is_garrafa: bool = False, doses_por_garrafa: float = 0.0,
                      preco_dose: float = 0.0, volume_garrafa_ml: int = VOLUME_GARRAFA_ML_PADRAO) -> tuple[bool, str]:
    import math
    nome = (nome or "").strip()
    categoria_nome = (categoria_nome or "").strip()
    codigo_barras = (codigo_barras or "").strip() or None
    try:
        quantidade = _inteiro_exato(quantidade, "Quantidade")
        estoque_minimo = _inteiro_exato(estoque_minimo, "Estoque mínimo")
        estoque_medio = _inteiro_exato(estoque_medio, "Estoque médio")
        preco, preco_custo = float(preco), float(preco_custo)
        doses_por_garrafa, preco_dose = float(doses_por_garrafa or 0), float(preco_dose or 0)
        volume_garrafa_ml = _inteiro_exato(volume_garrafa_ml, "Volume da garrafa")
    except QuantidadeInteiroInvalido as exc:
        return False, str(exc)
    except (TypeError, ValueError, OverflowError):
        return False, "Há campos numéricos inválidos."
    nums = [preco, preco_custo, doses_por_garrafa, preco_dose]
    if not nome:
        return False, "O nome do produto é obrigatório."
    if any(not math.isfinite(n) for n in nums):
        return False, "Valores numéricos precisam ser finitos."
    if quantidade < 0 or min(estoque_minimo, estoque_medio) < 0:
        return False, "Estoque e limites não podem ser negativos."
    if preco < 0 or preco_custo < 0 or preco_dose < 0:
        return False, "Preços e custos não podem ser negativos."
    if estoque_medio < estoque_minimo:
        return False, "O estoque médio deve ser maior ou igual ao estoque mínimo."
    if is_garrafa and (volume_garrafa_ml <= 0 or doses_por_garrafa <= 0 or preco_dose <= 0):
        return False, "Para garrafas, informe volume, rendimento de doses e preço da dose válidos."
    
    try:
        with get_db() as (conn, cur):
            _inserir_produto_cur(cur, nome, categoria_nome, quantidade, preco, codigo_barras,
                                 estoque_minimo, estoque_medio, preco_custo, is_garrafa,
                                 doses_por_garrafa, preco_dose, volume_garrafa_ml)
        return True, "Produto cadastrado com sucesso."
    except sqlite3.IntegrityError as exc:
        if "codigo_barras" in str(exc).lower():
            return False, "Código de barras já cadastrado."
        return False, "Já existe um produto com esse nome."
    except ValueError as exc:
        return False, str(exc)


def editar_produto_completo(produto_id: int, nome: str, categoria_nome: str, preco: float,
                            nova_quantidade: int, codigo_barras: str | None = None,
                            estoque_minimo: int | None = None, estoque_medio: int | None = None,
                            preco_custo: float | None = None, is_garrafa: bool | None = None,
                            doses_por_garrafa: float | None = None,
                            preco_dose: float | None = None,
                            volume_garrafa_ml: int | None = None) -> tuple[bool, str]:
    import math
    nome = (nome or "").strip()
    categoria_nome = (categoria_nome or "").strip()
    codigo_barras = (codigo_barras or "").strip() or None
    try:
        preco, nova_quantidade = float(preco), _inteiro_exato(nova_quantidade, "Quantidade")
        if preco_custo is not None: preco_custo = float(preco_custo)
        if estoque_minimo is not None: estoque_minimo = _inteiro_exato(estoque_minimo, "Estoque mínimo")
        if estoque_medio is not None: estoque_medio = _inteiro_exato(estoque_medio, "Estoque médio")
        if doses_por_garrafa is not None: doses_por_garrafa = float(doses_por_garrafa)
        if preco_dose is not None: preco_dose = float(preco_dose)
        if volume_garrafa_ml is not None: volume_garrafa_ml = _inteiro_exato(volume_garrafa_ml, "Volume da garrafa")
    except (TypeError, ValueError, OverflowError):
        return False, "Há campos numéricos inválidos."
    if not nome or nova_quantidade < 0 or not math.isfinite(preco) or preco < 0:
        return False, "Nome obrigatório; quantidade e preço devem ser válidos e não negativos."
    try:
        with get_db() as (conn, cur):
            atual = cur.execute("SELECT * FROM produtos WHERE id=? AND ativo=1", (produto_id,)).fetchone()
            if not atual:
                return False, "Produto não encontrado ou arquivado."
            custo = float(preco_custo if preco_custo is not None else atual['preco_custo'])
            min_q = int(estoque_minimo if estoque_minimo is not None else atual['estoque_minimo'])
            med_q = int(estoque_medio if estoque_medio is not None else atual['estoque_medio'])
            garrafa = bool(is_garrafa if is_garrafa is not None else atual['is_garrafa'])
            doses = float(doses_por_garrafa if doses_por_garrafa is not None else atual['doses_por_garrafa'])
            dose_preco = float(preco_dose if preco_dose is not None else atual['preco_dose'])
            volume = int(volume_garrafa_ml if volume_garrafa_ml is not None else atual['volume_garrafa_ml'])
            if not all(math.isfinite(x) for x in (custo,doses,dose_preco)) or custo < 0 or min_q < 0 or med_q < min_q:
                return False, "Custo, limites de estoque ou rendimento inválidos."
            if garrafa and (doses <= 0 or dose_preco <= 0 or volume <= 0):
                return False, "Para garrafas, informe volume, rendimento e preço de dose válidos."
            if codigo_barras:
                dup = cur.execute("SELECT id,nome FROM produtos WHERE codigo_barras=? AND ativo=1 AND id<>?", (codigo_barras,produto_id)).fetchone()
                if dup: return False, f"Código de barras já cadastrado em '{dup['nome']}'."
            cat_id = None
            if categoria_nome:
                row=cur.execute("SELECT id FROM categorias WHERE nome=?",(categoria_nome,)).fetchone()
                if row: cat_id=row['id']
                else:
                    cur.execute("INSERT INTO categorias(nome) VALUES(?)",(categoria_nome,)); cat_id=cur.lastrowid
            cur.execute("""UPDATE produtos SET nome=?,categoria_id=?,preco=?,quantidade=?,codigo_barras=?,
                estoque_minimo=?,estoque_medio=?,preco_custo=?,is_garrafa=?,doses_por_garrafa=?,preco_dose=?,
                volume_garrafa_ml=? WHERE id=?""",
                (nome,cat_id,preco,nova_quantidade,codigo_barras,min_q,med_q,custo,1 if garrafa else 0,doses,dose_preco,volume,produto_id))
            diff = nova_quantidade - int(atual['quantidade'])
            if diff:
                agora=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",
                            (produto_id,'ajuste',diff,agora,nome))
                cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                            (produto_id,'ajuste_estoque',f"Estoque alterado de {atual['quantidade']} para {nova_quantidade}",diff,agora,nome))
        return True, "Alterações salvas com sucesso."
    except sqlite3.IntegrityError as exc:
        if "codigo_barras" in str(exc).lower(): return False, "Código de barras já cadastrado."
        return False, "Já existe outro produto com esse nome."

def deletar_produto(produto_id: int) -> tuple[bool, str]:
    """Arquiva produto sem destruir histórico financeiro ou garrafas rastreadas."""
    with get_db() as (conn, cur):
        produto = cur.execute("SELECT nome FROM produtos WHERE id=? AND ativo=1", (produto_id,)).fetchone()
        if not produto:
            return False, "Produto não encontrado ou já arquivado."
        aberta = cur.execute("SELECT 1 FROM garrafas_abertas WHERE produto_id=? AND status='aberta' AND doses_restantes>0 LIMIT 1", (produto_id,)).fetchone()
        if aberta:
            return False, "Não é possível arquivar um produto que ainda tem garrafas abertas. Encerre-as primeiro."
        cur.execute("UPDATE produtos SET ativo=0 WHERE id=?", (produto_id,))
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                    (produto_id,'produto_arquivado','Produto arquivado; históricos preservados.',0,agora,produto['nome']))
    return True, "Produto arquivado. O histórico foi preservado."

def listar_produtos_arquivados(termo: str = "", limite: int = 250) -> list[dict[str, Any]]:
    """Lista produtos arquivados sem expô-los no catálogo operacional/PDV."""
    termo = (termo or "").strip()
    try:
        limite = max(1, min(int(limite), 500))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("O limite de produtos arquivados deve ser um inteiro positivo.")

    where = "WHERE p.ativo = 0"
    params: list[Any] = []
    if termo:
        where += " AND (unaccent(p.nome) LIKE unaccent(?) OR unaccent(COALESCE(c.nome,'')) LIKE unaccent(?) OR p.codigo_barras LIKE ?)"
        params.extend((f"%{termo}%", f"%{termo}%", f"%{termo}%"))

    query = f"""SELECT p.*, c.nome AS categoria_nome
                FROM produtos p LEFT JOIN categorias c ON p.categoria_id = c.id
                {where} ORDER BY p.nome LIMIT ?"""
    params.append(limite)
    with get_db() as (_, cur):
        cur.execute(query, params)
        return [_row_to_dict(row) for row in cur.fetchall()]


def restaurar_produto(produto_id: int) -> tuple[bool, str]:
    """Reativa um produto arquivado sem recriar ou apagar seus históricos."""
    try:
        with get_db() as (conn, cur):
            produto = cur.execute(
                "SELECT id, nome, codigo_barras, ativo FROM produtos WHERE id = ?",
                (produto_id,),
            ).fetchone()
            if not produto:
                return False, "Produto não encontrado."
            if int(produto["ativo"] or 0) == 1:
                return False, "Esse produto já está ativo."

            try:
                cur.execute("UPDATE produtos SET ativo = 1 WHERE id = ? AND ativo = 0", (produto_id,))
            except sqlite3.IntegrityError as exc:
                mensagem = str(exc).lower()
                if "codigo_barras" in mensagem or "idx_produto_codigo_barras_unico" in mensagem:
                    return False, "Não foi possível restaurar: o código de barras já pertence a outro produto ativo."
                if "produtos.nome" in mensagem or "unique constraint failed: produtos.nome" in mensagem:
                    return False, "Não foi possível restaurar: já existe um produto com esse nome."
                raise

            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cur.execute(
                "INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",
                (produto_id, "produto_restaurado", "Produto restaurado do arquivo.", 0, agora, produto["nome"]),
            )
        return True, f"Produto '{produto['nome']}' restaurado."
    except sqlite3.IntegrityError as exc:
        if "codigo_barras" in str(exc).lower():
            return False, "Não foi possível restaurar: o código de barras já pertence a outro produto ativo."
        return False, "Não foi possível restaurar o produto por conflito de dados."


def registrar_entrada(produto_id: int, qtd: int) -> tuple[bool, str]:
    try: qtd = _inteiro_exato(qtd, "Quantidade")
    except (TypeError, ValueError): return False, "A quantidade precisa ser um número inteiro válido."
    if qtd <= 0: return False, "A quantidade deve ser um inteiro maior que zero."
    with get_db() as (conn,cur):
        prod=cur.execute("SELECT nome,quantidade FROM produtos WHERE id=? AND ativo=1",(produto_id,)).fetchone()
        if not prod: return False, "Produto não encontrado ou arquivado."
        cur.execute("UPDATE produtos SET quantidade=quantidade+? WHERE id=? AND ativo=1",(qtd,produto_id))
        data=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",(produto_id,'entrada',qtd,data,prod['nome']))
        cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",(produto_id,'entrada',f"Entrada de {qtd} unidades",qtd,data,prod['nome']))
    return True, f"Entrada de {qtd} un. de '{prod['nome']}' registrada."

def registrar_saida(produto_id: int, qtd: int) -> tuple[bool, str]:
    try: qtd = _inteiro_exato(qtd, "Quantidade")
    except (TypeError, ValueError): return False, "A quantidade precisa ser um número inteiro válido."
    if qtd <= 0: return False, "A quantidade deve ser um inteiro maior que zero."
    with get_db() as (conn,cur):
        prod=cur.execute("SELECT nome,quantidade FROM produtos WHERE id=? AND ativo=1",(produto_id,)).fetchone()
        if not prod: return False, "Produto não encontrado ou arquivado."
        if prod['quantidade'] < qtd: return False, f"Estoque insuficiente. Disponível: {prod['quantidade']} un."
        cur.execute("UPDATE produtos SET quantidade=quantidade-? WHERE id=? AND quantidade>=?",(qtd,produto_id,qtd))
        if cur.rowcount != 1: return False, "O estoque mudou durante a operação; atualize a lista e tente novamente."
        data=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT INTO historico(produto_id,tipo,quantidade,data,nome_produto) VALUES(?,?,?,?,?)",(produto_id,'saida',qtd,data,prod['nome']))
        cur.execute("INSERT INTO auditoria(produto_id,acao,descricao,quantidade,data,nome_produto) VALUES(?,?,?,?,?,?)",(produto_id,'saida_manual',f"Saída manual de {qtd} unidades",qtd,data,prod['nome']))
    return True, f"Saída de {qtd} un. de '{prod['nome']}' registrada."


# [CORREÇÃO] Importação de CSV 100% Transacional e com suporte a campos completos.
def importar_csv(caminho_arquivo: str) -> tuple[int, int, list[str]]:
    total = 0
    importados = 0
    erros = []
    
    try:
        with open(caminho_arquivo, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            total = len(rows)

        if not rows:
            return 0, 0, ["O arquivo CSV está vazio."]

        # 1. Fase de Validação (Nada é gravado ainda)
        validos = []
        for num_linha, row in enumerate(rows, start=2):
            nome = (row.get('nome') or '').strip()
            if not nome:
                erros.append(f"Linha {num_linha}: nome vazio.")
                continue
            
            try:
                qtd = _inteiro_exato(row.get('quantidade', '0') or '0', f"Linha {num_linha} (quantidade)")
                preco = float((row.get('preco') or '0').strip().replace(',', '.'))
                custo = float((row.get('preco_custo') or '0').strip().replace(',', '.'))
                cod_barras = (row.get('codigo_barras') or '').strip() or None
                est_min = _inteiro_exato(row.get('estoque_minimo', '5') or '5', f"Linha {num_linha} (estoque_minimo)")
                est_med = _inteiro_exato(row.get('estoque_medio', '15') or '15', f"Linha {num_linha} (estoque_medio)")
                is_g = (row.get('is_garrafa') or '').strip().lower() in ('1', 'true', 'sim', 'yes')
                doses = float((row.get('doses_por_garrafa') or '5.7').strip().replace(',', '.'))
                p_dose = float((row.get('preco_dose') or '0').strip().replace(',', '.'))
                vol = _inteiro_exato(row.get('volume_garrafa_ml', '900') or '900', f"Linha {num_linha} (volume)")
            except (ValueError, TypeError, QuantidadeInteiroInvalido) as e:
                erros.append(f"Linha {num_linha}: valor inválido ({e}).")
                continue

            validos.append((num_linha, nome, (row.get('categoria') or '').strip(), qtd, preco, custo, cod_barras, est_min, est_med, is_g, doses, p_dose, vol))

        if not validos:
            return total, 0, erros

        # 2. Fase de Gravação (Transação Única)
        try:
            with get_db() as (conn, cur):
                for (num_linha, nome, cat, qtd, preco, custo, cod, est_min, est_med, is_g, doses, p_dose, vol) in validos:
                    try:
                        _inserir_produto_cur(cur, nome, cat, qtd, preco, cod, est_min, est_med, custo, is_g, doses, p_dose, vol)
                        importados += 1
                    except sqlite3.IntegrityError as e:
                        raise ValueError(f"Linha {num_linha} ({nome}): conflito de dados ({e}).")
        except Exception as e:
            # Em caso de qualquer erro no meio da transação, rollback automático do get_db.
            return total, 0, erros + [f"Importação cancelada (nenhum produto foi salvo): {e}"]

        return total, importados, erros

    except FileNotFoundError:
        return 0, 0, ["Arquivo não encontrado."]
    except Exception as e:
        return 0, 0, [f"Erro ao ler CSV: {e!s}"]