"""Esquema e migrações aditivas; nunca elimina dados históricos."""
import logging
import sqlite3
from datetime import datetime
from infrastructure.database.connection import get_db
from domain.bottle_rules import calcular_doses_estimadas, VOLUME_GARRAFA_ML_PADRAO

log = logging.getLogger(__name__)


def _colunas(cur, tabela: str) -> set[str]:
    return {r["name"] for r in cur.execute(f"PRAGMA table_info({tabela})").fetchall()}


def _garantir_coluna(cur, tabela: str, nome: str, definicao: str) -> bool:
    if nome in _colunas(cur, tabela):
        return False
    cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao}")
    return True


def criar_tabelas():
    """Cria tabelas e aplica migrações incrementais de forma idempotente."""
    with get_db() as (conn, cur):
        cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        cur.execute("""CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE,
            categoria_id INTEGER, quantidade INTEGER NOT NULL DEFAULT 0,
            preco REAL NOT NULL DEFAULT 0.0, preco_custo REAL NOT NULL DEFAULT 0.0,
            codigo_barras TEXT, estoque_minimo INTEGER NOT NULL DEFAULT 5,
            estoque_medio INTEGER NOT NULL DEFAULT 15, is_garrafa INTEGER NOT NULL DEFAULT 0,
            doses_por_garrafa REAL NOT NULL DEFAULT 5.7, preco_dose REAL NOT NULL DEFAULT 0.0,
            volume_garrafa_ml INTEGER NOT NULL DEFAULT 900, ativo INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, tipo TEXT,
            quantidade REAL, data TEXT, nome_produto TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE SET NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER, acao TEXT,
            descricao TEXT, quantidade REAL, data TEXT, nome_produto TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE SET NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS dias_operacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data_abertura TEXT NOT NULL,
            horario_abertura TEXT NOT NULL, data_fechamento TEXT,
            horario_fechamento TEXT, status TEXT NOT NULL DEFAULT 'aberto',
            total_vendido_fechamento REAL, total_recebido_fechamento REAL,
            fiado_aberto_fechamento REAL, total_descontos_fechamento REAL,
            lucro_estimado_fechamento REAL, quantidade_vendas_fechamento INTEGER)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, dia_operacao_id INTEGER,
            data TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'finalizado',
            forma_pagamento TEXT, desconto_percentual REAL NOT NULL DEFAULT 0.0,
            desconto_valor REAL NOT NULL DEFAULT 0.0, total_bruto REAL NOT NULL,
            total_liquido REAL NOT NULL, lucro_total REAL NOT NULL DEFAULT 0.0,
            observacao TEXT, cliente_nome TEXT, cancelada_em TEXT,
            FOREIGN KEY (dia_operacao_id) REFERENCES dias_operacao(id))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS venda_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT, venda_id INTEGER NOT NULL,
            produto_id INTEGER, nome_produto TEXT, quantidade REAL NOT NULL,
            preco_unitario REAL NOT NULL, preco_custo REAL NOT NULL DEFAULT 0.0,
            desconto_percentual REAL NOT NULL DEFAULT 0.0, desconto_valor REAL NOT NULL DEFAULT 0.0,
            subtotal_bruto REAL NOT NULL, subtotal REAL NOT NULL,
            lucro_item REAL NOT NULL DEFAULT 0.0, tipo TEXT NOT NULL DEFAULT 'unidade',
            desconto_geral_rateado REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE,
            FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE SET NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS garrafas_abertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL,
            data_abertura TEXT NOT NULL, doses_restantes REAL NOT NULL,
            perdas_doses REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'aberta',
            doses_iniciais REAL NOT NULL DEFAULT 0, data_fechamento TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS perdas_registro (
            id INTEGER PRIMARY KEY AUTOINCREMENT, garrafa_aberta_id INTEGER,
            produto_id INTEGER, quantidade REAL NOT NULL, motivo TEXT,
            data TEXT NOT NULL,
            FOREIGN KEY (garrafa_aberta_id) REFERENCES garrafas_abertas(id) ON DELETE SET NULL,
            FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE SET NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS venda_pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, venda_id INTEGER NOT NULL,
            forma_pagamento TEXT NOT NULL CHECK (forma_pagamento IN ('Dinheiro','Cartão','Pix')),
            valor REAL NOT NULL CHECK (valor >= 0), data TEXT NOT NULL, dia_operacao_id INTEGER,
            FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE RESTRICT,
            FOREIGN KEY (dia_operacao_id) REFERENCES dias_operacao(id))""")

        # Compatibilidade com versões anteriores do banco.
        additions = {
            "produtos": [
                ("categoria_id", "INTEGER REFERENCES categorias(id) ON DELETE SET NULL"),
                ("estoque_minimo", "INTEGER NOT NULL DEFAULT 5"),
                ("estoque_medio", "INTEGER NOT NULL DEFAULT 15"),
                ("preco_custo", "REAL NOT NULL DEFAULT 0.0"),
                ("doses_por_garrafa", "REAL NOT NULL DEFAULT 5.7"),
                ("preco_dose", "REAL NOT NULL DEFAULT 0.0"),
                ("is_garrafa", "INTEGER NOT NULL DEFAULT 0"),
                ("volume_garrafa_ml", "INTEGER NOT NULL DEFAULT 900"),
                ("ativo", "INTEGER NOT NULL DEFAULT 1"),
            ],
            "dias_operacao": [
                ("total_vendido_fechamento", "REAL"),
                ("total_recebido_fechamento", "REAL"),
                ("fiado_aberto_fechamento", "REAL"),
                ("total_descontos_fechamento", "REAL"),
                ("lucro_estimado_fechamento", "REAL"),
                ("quantidade_vendas_fechamento", "INTEGER"),
            ],
            "vendas": [
                ("dia_operacao_id", "INTEGER REFERENCES dias_operacao(id)"),
                ("lucro_total", "REAL NOT NULL DEFAULT 0.0"),
                ("observacao", "TEXT"), ("cliente_nome", "TEXT"), ("cancelada_em", "TEXT"),
            ],
            "venda_itens": [
                ("desconto_percentual", "REAL NOT NULL DEFAULT 0.0"),
                ("desconto_valor", "REAL NOT NULL DEFAULT 0.0"),
                ("subtotal_bruto", "REAL NOT NULL DEFAULT 0.0"),
                ("preco_custo", "REAL NOT NULL DEFAULT 0.0"),
                ("lucro_item", "REAL NOT NULL DEFAULT 0.0"),
                ("tipo", "TEXT NOT NULL DEFAULT 'unidade'"),
                ("desconto_geral_rateado", "REAL NOT NULL DEFAULT 0.0"),
            ],
            "garrafas_abertas": [
                ("perdas_doses", "REAL NOT NULL DEFAULT 0"),
                ("status", "TEXT NOT NULL DEFAULT 'aberta'"),
                ("doses_iniciais", "REAL NOT NULL DEFAULT 0"),
                ("data_fechamento", "TEXT"),
            ],
            "venda_pagamentos": [
                ("dia_operacao_id", "INTEGER REFERENCES dias_operacao(id)"),
            ],
        }
        
        newly_added = set()
        for table, columns in additions.items():
            for name, definition in columns:
                if _garantir_coluna(cur, table, name, definition):
                    newly_added.add((table, name))

        # Atribui estado histórico sem apagar nem recriar registros.
        if ("garrafas_abertas", "status") in newly_added:
            cur.execute("UPDATE garrafas_abertas SET status = CASE WHEN doses_restantes > 0 THEN 'aberta' ELSE 'fechada' END")
        if ("garrafas_abertas", "doses_iniciais") in newly_added:
            cur.execute("""UPDATE garrafas_abertas SET doses_iniciais = MAX(
                COALESCE((SELECT p.doses_por_garrafa FROM produtos p WHERE p.id=garrafas_abertas.produto_id), doses_restantes),
                COALESCE(doses_restantes, 0))""")
        
        # [CORREÇÃO] Garante que a migração de is_garrafa só rode quando a coluna for criada.
        # Isso evita que o aplicativo sobrescreva a escolha do usuário em toda inicialização.
        if ("produtos", "is_garrafa") in newly_added:
            cur.execute("UPDATE produtos SET is_garrafa = 1 WHERE preco_dose > 0 AND is_garrafa = 0")

        # [CORREÇÃO] Migrações legadas de vendas devem rodar apenas quando a coluna for criada.
        if ("vendas", "dia_operacao_id") in newly_added:
            cur.execute("""UPDATE venda_pagamentos SET dia_operacao_id =
                (SELECT v.dia_operacao_id FROM vendas v WHERE v.id = venda_pagamentos.venda_id)
                WHERE dia_operacao_id IS NULL""")
            cur.execute("UPDATE vendas SET forma_pagamento='Fiado' WHERE status='pendente'")
            cur.execute("""INSERT INTO venda_pagamentos(venda_id, forma_pagamento, valor, data, dia_operacao_id)
                SELECT v.id, v.forma_pagamento, v.total_liquido, v.data, v.dia_operacao_id
                FROM vendas v WHERE v.status = 'finalizado'
                  AND v.forma_pagamento IN ('Dinheiro','Cartão','Pix') AND v.total_liquido > 0
                  AND NOT EXISTS (SELECT 1 FROM venda_pagamentos p WHERE p.venda_id = v.id)""")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_vendas_dia_status ON vendas(dia_operacao_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_venda_itens_venda ON venda_itens(venda_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_garrafas_produto_status ON garrafas_abertas(produto_id, status, data_abertura)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_venda_pagamentos_venda ON venda_pagamentos(venda_id, id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_venda_pagamentos_dia ON venda_pagamentos(dia_operacao_id, forma_pagamento)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_historico_data ON historico(data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria(data)")
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dia_operacao_unico_aberto ON dias_operacao(status) WHERE status = 'aberto'")
        except sqlite3.IntegrityError:
            log.warning("A base antiga tem mais de um dia aberto; índice de unicidade não foi criado.")
        # Não falha migração antiga se já existir código de barras duplicado.
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_produto_codigo_barras_unico ON produtos(codigo_barras) WHERE ativo=1 AND codigo_barras IS NOT NULL AND codigo_barras <> ''")
        except sqlite3.IntegrityError:
            log.warning("Há códigos de barras duplicados na base antiga; índice único não foi criado.")
        stamp_migration = datetime.now().isoformat(timespec="seconds")
        cur.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (1, ?)", (stamp_migration,))
        cur.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (2, ?)", (stamp_migration,))


def popular_exemplos():
    """Insere dados demonstrativos somente quando chamado explicitamente."""
    with get_db() as (conn, cur):
        if cur.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] > 0:
            return
        categorias = ["Refrigerante", "Suco", "Cerveja", "Destilado", "Vinho"]
        for cat in categorias:
            cur.execute("INSERT OR IGNORE INTO categorias (nome) VALUES (?)", (cat,))
        mapa = {r["nome"]: r["id"] for r in cur.execute("SELECT id,nome FROM categorias").fetchall()}
        examples = [
            ("Refrigerante Guaraná 350ml", mapa["Refrigerante"], 40, 4.00, 2.50, 10, 25),
            ("Refrigerante Coca-Cola 350ml", mapa["Refrigerante"], 40, 5.00, 3.00, 8, 20),
            ("Suco Del-Valle 290ml", mapa["Suco"], 35, 5.00, 3.00, 6, 18),
            ("Cerveja Pilsen 600ml", mapa["Cerveja"], 50, 8.50, 4.50, 15, 30),
            ("Vinho Tinto Seco 750ml", mapa["Vinho"], 20, 35.00, 20.00, 5, 12),
        ]
        for nome, cat, qtd, preco, custo, minimo, medio in examples:
            cur.execute("INSERT INTO produtos(nome,categoria_id,quantidade,preco,preco_custo,estoque_minimo,estoque_medio) VALUES(?,?,?,?,?,?,?)", (nome,cat,qtd,preco,custo,minimo,medio))
        _, yield_est = calcular_doses_estimadas()
        cur.execute("INSERT INTO produtos(nome,categoria_id,quantidade,preco,preco_custo,estoque_minimo,estoque_medio,is_garrafa,doses_por_garrafa,preco_dose,volume_garrafa_ml) VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("Whisky Escocês 900ml", mapa["Destilado"], 10,90.00,55.00,3,8,1,yield_est,18.00,VOLUME_GARRAFA_ML_PADRAO))