"""Testes de regressão do núcleo de negócio. Não exigem interface gráfica."""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

# Permite executar tanto ``python tests/test_core.py`` quanto unittest discover.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import database
from services import backup_service
from domain.autocomplete_rules import selecionar_sugestao
from services.backup_service import criar_backup


class TesteNucleoBARNS(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="barns_test_")
        self.db_path = str(Path(self.temp.name) / "adega_dados.db")
        os.environ["BARNS_DB_PATH"] = self.db_path
        database.criar_tabelas()
        self.dia_id, opened = database.abrir_dia()
        self.assertTrue(opened)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("BARNS_DB_PATH", None)

    def produto(self, nome="Produto Teste", qtd=10, preco=10.0, custo=4.0,
                garrafa=False, doses=5.7, preco_dose=20.0):
        ok, mensagem = database.adicionar_produto(
            nome, "Testes", qtd, preco, preco_custo=custo,
            is_garrafa=garrafa, doses_por_garrafa=doses if garrafa else 0,
            preco_dose=preco_dose if garrafa else 0,
            volume_garrafa_ml=900,
        )
        self.assertTrue(ok, mensagem)
        return next(p for p in database.buscar_produtos("") if p["nome"] == nome)

    def item(self, p, qtd=1, tipo="unidade", preco=None, desconto=0):
        return {"produto_id": p["id"], "nome": ("Dose: " if tipo == "dose" else "") + p["nome"],
                "preco": p["preco_dose"] if tipo == "dose" and preco is None else (p["preco"] if preco is None else preco),
                "quantidade": qtd, "tipo": tipo, "desconto_percentual": desconto}

    def test_produto_arquivado_fica_consultavel_e_pode_ser_restaurado(self):
        produto = self.produto(nome="Produto Arquivável", qtd=5)
        ok, msg = database.deletar_produto(produto["id"])
        self.assertTrue(ok, msg)
        self.assertFalse(any(p["id"] == produto["id"] for p in database.buscar_produtos("")))
        arquivados = database.listar_produtos_arquivados("Arquivável")
        self.assertEqual([p["id"] for p in arquivados], [produto["id"]])
        ok, msg = database.restaurar_produto(produto["id"])
        self.assertTrue(ok, msg)
        self.assertTrue(any(p["id"] == produto["id"] for p in database.buscar_produtos("")))
        self.assertFalse(database.listar_produtos_arquivados("Arquivável"))

    def test_restauracao_rejeita_codigo_de_barras_em_uso(self):
        p1_ok, p1_msg = database.adicionar_produto("Produto Antigo", "Testes", 2, 5.0, codigo_barras="123456")
        self.assertTrue(p1_ok, p1_msg)
        antigo = next(p for p in database.buscar_produtos("") if p["nome"] == "Produto Antigo")
        ok, msg = database.deletar_produto(antigo["id"])
        self.assertTrue(ok, msg)
        p2_ok, p2_msg = database.adicionar_produto("Produto Novo", "Testes", 2, 5.0, codigo_barras="123456")
        self.assertTrue(p2_ok, p2_msg)
        ok, msg = database.restaurar_produto(antigo["id"])
        self.assertFalse(ok)
        self.assertIn("código de barras", msg.lower())
        self.assertEqual(len(database.listar_produtos_arquivados()), 1)

    def test_quantidade_negativa_e_rejeitada_sem_mudar_estoque(self):
        p = self.produto(qtd=10)
        with self.assertRaises(ValueError):
            database.registrar_venda_completa([self.item(p, qtd=-1)], "Dinheiro", 0,
                                              "finalizado", self.dia_id)
        fresh = next(p for p in database.buscar_produtos("") if p["nome"] == "Produto Teste")
        self.assertEqual(fresh["quantidade"], 10)
        self.assertEqual(database.listar_vendas(), [])

    def test_busca_exata_fica_primeiro_mesmo_com_limite(self):
        ok, msg = database.adicionar_produto("Produto Exato", "Z - Última Categoria", 2, 8.0)
        self.assertTrue(ok, msg)
        ok, msg = database.adicionar_produto("Produto Exato - Variante", "A - Primeira Categoria", 2, 7.0)
        self.assertTrue(ok, msg)
        resultados = database.buscar_produtos("Produto Exato", limite=1)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["nome"], "Produto Exato")

    def test_autocomplete_enter_prioriza_item_destacado(self):
        opcoes = ["Cerveja Pilsen — R$ 5.00", "Cerveja Puro Malte — R$ 6.00"]
        self.assertEqual(selecionar_sugestao("Cerveja", opcoes, opcoes[1]), opcoes[1])

    def test_autocomplete_enter_prioriza_correspondencia_exata_sem_acento(self):
        opcoes = ["Cerveja Lager — R$ 5.00", "Café — R$ 4.00"]
        self.assertEqual(selecionar_sugestao("cafe", opcoes), opcoes[1])

    def test_autocomplete_enter_adota_primeira_sugestao_para_busca_parcial(self):
        opcoes = ["Coca-Cola 2L — R$ 12.00", "Coca-Cola Zero 2L — R$ 12.00"]
        self.assertEqual(selecionar_sugestao("coca", opcoes), opcoes[0])

    def test_paginacao_dias_retorna_todos_os_registros_sem_exclusao(self):
        with database.get_db() as (_, cur):
            for indice in range(60):
                cur.execute(
                    "INSERT INTO dias_operacao(data_abertura, horario_abertura, data_fechamento, horario_fechamento, status) "
                    "VALUES(?, ?, ?, ?, 'fechado')",
                    (f"{(indice % 28) + 1:02d}/09/2026", "09:00:00", f"{(indice % 28) + 1:02d}/09/2026", "18:00:00"),
                )
        total = database.contar_dias_operacao()
        pagina1 = database.listar_dias_operacao(limite=25, offset=0)
        pagina2 = database.listar_dias_operacao(limite=25, offset=25)
        pagina3 = database.listar_dias_operacao(limite=25, offset=50)
        self.assertEqual(total, 61)  # inclui o dia aberto criado no setUp
        self.assertEqual([len(pagina1), len(pagina2), len(pagina3)], [25, 25, 11])
        ids = [dia["id"] for pagina in (pagina1, pagina2, pagina3) for dia in pagina]
        self.assertEqual(len(ids), total)
        self.assertEqual(len(set(ids)), total)
        self.assertEqual(database.contar_dias_operacao(), 61)

    def test_busca_de_venda_por_id_e_total_de_fiado_nao_carregam_lista_inteira(self):
        produto = self.produto(qtd=3, preco=12.0)
        pendente_id = database.registrar_venda_completa(
            [self.item(produto)], "Dinheiro", 0, "pendente", self.dia_id,
            cliente_nome="Cliente Teste",
        )
        outra_id = database.registrar_venda_completa(
            [self.item(produto)], "Dinheiro", 0, "pendente", self.dia_id,
            cliente_nome="Outro Cliente",
        )
        uma_venda = database.listar_vendas(status="pendente", venda_id=pendente_id)
        self.assertEqual([v["id"] for v in uma_venda], [pendente_id])
        self.assertEqual(database.obter_total_fiado_aberto(), 24.0)
        self.assertNotEqual(pendente_id, outra_id)

    def test_paginacao_vendas_retorna_todas_as_vendas_sem_limite_oculto(self):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with database.get_db() as (_, cur):
            for indice in range(57):
                cur.execute(
                    "INSERT INTO vendas(dia_operacao_id, data, status, forma_pagamento, total_bruto, total_liquido) "
                    "VALUES(?, ?, 'finalizado', 'Dinheiro', 10, 10)",
                    (self.dia_id, agora),
                )
        total = database.contar_vendas()
        pagina1 = database.listar_vendas(limite=25, offset=0)
        pagina2 = database.listar_vendas(limite=25, offset=25)
        pagina3 = database.listar_vendas(limite=25, offset=50)
        self.assertEqual(total, 57)
        self.assertEqual([len(pagina1), len(pagina2), len(pagina3)], [25, 25, 7])
        ids = [venda["id"] for pagina in (pagina1, pagina2, pagina3) for venda in pagina]
        self.assertEqual(len(set(ids)), 57)
        self.assertEqual(database.contar_vendas(status="pendente"), 0)

    def test_paginacao_historico_permite_consultar_registros_apos_os_primeiros_200(self):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with database.get_db() as (_, cur):
            for indice in range(67):
                cur.execute(
                    "INSERT INTO historico(produto_id, tipo, quantidade, data, nome_produto) VALUES(NULL, 'entrada', ?, ?, ?)",
                    (indice + 1, agora, f"Produto histórico {indice:03d}"),
                )
        total = database.contar_historico_completo()
        pagina1 = database.buscar_historico_completo(limite=30, offset=0)
        pagina2 = database.buscar_historico_completo(limite=30, offset=30)
        pagina3 = database.buscar_historico_completo(limite=30, offset=60)
        self.assertEqual(total, 67)
        self.assertEqual([len(pagina1), len(pagina2), len(pagina3)], [30, 30, 7])
        chaves = [(item["origem"], item["registro_id"]) for pagina in (pagina1, pagina2, pagina3) for item in pagina]
        self.assertEqual(len(chaves), 67)
        self.assertEqual(len(set(chaves)), 67)
        filtrado = database.contar_historico_completo(data=agora.split()[0])
        self.assertEqual(filtrado, 67)

    def test_busca_de_produtos_pode_limitar_resultados_para_autocomplete(self):
        for indice in range(12):
            ok, mensagem = database.adicionar_produto(f"Refrigerante {indice:02d}", "Bebidas", 2, 5.0)
            self.assertTrue(ok, mensagem)
        self.assertEqual(len(database.buscar_produtos("Refrigerante", limite=5)), 5)
        self.assertEqual(len(database.buscar_produtos("Refrigerante")), 12)
        with self.assertRaises(ValueError):
            database.buscar_produtos("Refrigerante", limite="inválido")

    def test_quantidades_fracionarias_nao_sao_truncadas_em_movimentacoes(self):
        ok, mensagem = database.adicionar_produto("Produto Fracionado", "Testes", 2.7, 10.0)
        self.assertFalse(ok)
        self.assertIn("inteiro", mensagem.lower())
        p = self.produto(nome="Produto Inteiro", qtd=4)
        ok, mensagem = database.registrar_entrada(p["id"], 1.5)
        self.assertFalse(ok)
        self.assertIn("inteiro", mensagem.lower())
        ok, mensagem = database.registrar_saida(p["id"], 1.5)
        self.assertFalse(ok)
        self.assertIn("inteiro", mensagem.lower())
        fresh = next(x for x in database.buscar_produtos("") if x["id"] == p["id"])
        self.assertEqual(fresh["quantidade"], 4)

    def test_desconto_geral_acima_de_cem_porcento_e_rejeitado(self):
        p = self.produto()
        with self.assertRaises(ValueError):
            database.registrar_venda_completa([self.item(p)], "Dinheiro", 101,
                                              "finalizado", self.dia_id)
        self.assertEqual(database.listar_vendas(), [])
        fresh = next(p for p in database.buscar_produtos("") if p["nome"] == "Produto Teste")
        self.assertEqual(fresh["quantidade"], 10)

    def test_descontos_lucro_e_pagamentos_mistos_conciliam(self):
        p = self.produto(qtd=10, preco=10, custo=4)
        venda_id = database.registrar_venda_completa(
            [self.item(p, qtd=2, desconto=10)], "Misto", 10, "finalizado", self.dia_id,
            pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 6.20},
                        {"forma_pagamento": "Pix", "valor": 10.00}],
        )
        venda = next(v for v in database.listar_vendas() if v["id"] == venda_id)
        self.assertAlmostEqual(venda["total_bruto"], 20.00, places=2)
        self.assertAlmostEqual(venda["desconto_valor"], 1.80, places=2)
        self.assertAlmostEqual(venda["total_liquido"], 16.20, places=2)
        self.assertAlmostEqual(sum(i["subtotal"] for i in venda["itens"]), venda["total_liquido"], places=2)
        self.assertAlmostEqual(sum(i["desconto_geral_rateado"] for i in venda["itens"]), 1.80, places=2)
        self.assertAlmostEqual(venda["lucro_total"], 8.20, places=2)
        self.assertEqual({x["forma_pagamento"] for x in venda["pagamentos"]}, {"Dinheiro", "Pix"})
        self.assertAlmostEqual(sum(x["valor"] for x in venda["pagamentos"]), 16.20, places=2)
        resumo_pagamento = {r["forma_pagamento"]: r["total_liquido"] for r in database.obter_resumo_pagamentos_dia(self.dia_id)}
        self.assertAlmostEqual(resumo_pagamento["Dinheiro"], 6.20, places=2)
        self.assertAlmostEqual(resumo_pagamento["Pix"], 10.00, places=2)

    def test_listar_vendas_carrega_itens_pagamentos_em_lote_e_respeita_limite(self):
        p = self.produto(nome="Refrigerante", qtd=10, preco=10, custo=4)
        ids = []
        for _ in range(3):
            ids.append(database.registrar_venda_completa(
                [self.item(p)], "Dinheiro", 0, "finalizado", self.dia_id,
                pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 10}],
            ))

        vendas = database.listar_vendas(limite=2)
        self.assertEqual([v["id"] for v in vendas], list(reversed(ids[-2:])))
        for venda in vendas:
            self.assertEqual(len(venda["itens"]), 1)
            self.assertEqual(len(venda["pagamentos"]), 1)
            self.assertEqual(venda["pagamentos"][0]["forma_pagamento"], "Dinheiro")
        with self.assertRaises(ValueError):
            database.listar_vendas(limite=0)

    def test_pagamento_misto_incorreto_nao_registra_venda(self):
        p = self.produto()
        with self.assertRaises(ValueError):
            database.registrar_venda_completa(
                [self.item(p)], "Misto", 0, "finalizado", self.dia_id,
                pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 2},
                            {"forma_pagamento": "Pix", "valor": 3}],
            )
        self.assertEqual(database.listar_vendas(), [])

    def test_venda_sem_dia_aberto_e_rejeitada(self):
        p = self.produto()
        database.fechar_dia(self.dia_id)
        with self.assertRaises(ValueError):
            database.registrar_venda_completa([self.item(p)], "Dinheiro", 0,
                                              "finalizado", self.dia_id)
        self.assertEqual(database.listar_vendas(), [])

    def test_dose_exige_confirmacao_para_abrir_garrafa(self):
        p = self.produto(nome="Whisky", qtd=2, preco=100, custo=50, garrafa=True, doses=5.7, preco_dose=20)
        itens = [self.item(p, qtd=3, tipo="dose")]
        with self.assertRaisesRegex(ValueError, "confirmar a abertura"):
            database.registrar_venda_completa(itens, "Dinheiro", 0, "finalizado", self.dia_id,
                                              pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 60}])
        fresh = next(x for x in database.buscar_produtos("") if x["id"] == p["id"])
        self.assertEqual(fresh["quantidade"], 2)
        self.assertEqual(database.obter_doses_disponiveis(p["id"]), 0)
        venda_id = database.registrar_venda_completa(
            itens, "Dinheiro", 0, "finalizado", self.dia_id,
            garrafas_autorizadas=[p["id"]],
            pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 60}],
        )
        self.assertGreater(venda_id, 0)
        fresh = next(x for x in database.buscar_produtos("") if x["id"] == p["id"])
        self.assertEqual(fresh["quantidade"], 1)
        self.assertAlmostEqual(database.obter_doses_disponiveis(p["id"]), 2.7, places=2)
        venda = next(v for v in database.listar_vendas() if v["id"] == venda_id)
        # O custo por dose usa o rendimento estimado 5,7, sem truncar para 5.
        self.assertAlmostEqual(venda["lucro_total"], 33.69, places=2)

    def test_falha_no_meio_da_venda_reverte_abertura_e_consume_nada(self):
        p = self.produto(nome="Whisky", qtd=1, preco=100, custo=50, garrafa=True, doses=5.7, preco_dose=20)
        itens = [self.item(p, qtd=1, tipo="dose"), self.item(p, qtd=1, tipo="unidade")]
        with self.assertRaisesRegex(ValueError, "Estoque insuficiente"):
            database.registrar_venda_completa(
                itens, "Dinheiro", 0, "finalizado", self.dia_id,
                garrafas_autorizadas=[p["id"]],
                pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 120}],
            )
        fresh = next(x for x in database.buscar_produtos("") if x["id"] == p["id"])
        self.assertEqual(fresh["quantidade"], 1)
        self.assertEqual(database.obter_doses_disponiveis(p["id"]), 0)
        self.assertEqual(database.listar_vendas(), [])

    def test_garrafa_encerrada_nao_pode_ser_reativada(self):
        p = self.produto(nome="Vodka", qtd=2, preco=70, custo=35, garrafa=True, doses=5.7, preco_dose=15)
        ok, msg, gid = database.abrir_garrafa(p["id"])
        self.assertTrue(ok, msg)
        ok, msg = database.fechar_garrafa(gid)
        self.assertTrue(ok, msg)
        ok, msg = database.ajustar_doses_restantes(gid, 3)
        self.assertFalse(ok)
        self.assertIn("encerrada", msg.lower())
        self.assertEqual(database.obter_doses_disponiveis(p["id"]), 0)

    def test_fifo_consumo_primeiro_garrafa_aberta_mais_antiga(self):
        p = self.produto(nome="Gin", qtd=3, preco=90, custo=45, garrafa=True, doses=5.7, preco_dose=18)
        ok, _, first = database.abrir_garrafa(p["id"])
        self.assertTrue(ok)
        ok, _, second = database.abrir_garrafa(p["id"])
        self.assertTrue(ok)
        self.assertTrue(database.ajustar_doses_restantes(first, 1)[0])
        venda_id = database.registrar_venda_completa(
            [self.item(p, qtd=2, tipo="dose")], "Dinheiro", 0, "finalizado", self.dia_id,
            pagamentos=[{"forma_pagamento": "Dinheiro", "valor": 36}],
        )
        bottles = {b["id"]: b for b in database.obter_garrafas_abertas(p["id"])}
        self.assertNotIn(first, bottles)
        self.assertAlmostEqual(bottles[second]["doses_restantes"], 4.7, places=2)

    def test_fiado_baixa_estoque_e_so_quita_com_pagamento_total(self):
        p = self.produto(qtd=4, preco=12, custo=5)
        venda_id = database.registrar_venda_completa([self.item(p)], "Dinheiro", 0,
            "pendente", self.dia_id, cliente_nome="Cliente Teste")
        venda = next(v for v in database.listar_vendas(status="pendente") if v["id"] == venda_id)
        self.assertEqual(venda["forma_pagamento"], "Fiado")
        self.assertEqual(venda["pagamentos"], [])
        fresh = next(x for x in database.buscar_produtos("") if x["nome"] == "Produto Teste")
        self.assertEqual(fresh["quantidade"], 3)
        with self.assertRaises(ValueError):
            database.atualizar_status_venda(venda_id, "finalizado", [{"forma_pagamento":"Dinheiro","valor":5}])
        database.atualizar_status_venda(venda_id, "finalizado", [
            {"forma_pagamento":"Dinheiro","valor":7}, {"forma_pagamento":"Pix","valor":5}
        ])
        quitada = next(v for v in database.listar_vendas() if v["id"] == venda_id)
        self.assertEqual(quitada["status"], "finalizado")
        self.assertEqual(quitada["forma_pagamento"], "Fiado")
        self.assertEqual({x["forma_pagamento"] for x in quitada["pagamentos"]}, {"Dinheiro", "Pix"})
        self.assertAlmostEqual(sum(x["valor"] for x in quitada["pagamentos"]), 12.00, places=2)

    def test_recebimento_de_fiado_e_lancado_no_dia_em_que_foi_recebido(self):
        p = self.produto(qtd=4, preco=12, custo=5)
        venda_id = database.registrar_venda_completa(
            [self.item(p)], "Dinheiro", 0, "pendente", self.dia_id, cliente_nome="Cliente Teste"
        )
        database.fechar_dia(self.dia_id)
        dia_recebimento_id, abriu = database.abrir_dia()
        self.assertTrue(abriu)
        database.atualizar_status_venda(venda_id, "finalizado", [
            {"forma_pagamento": "Pix", "valor": 12}
        ])
        resumo_original = database.obter_resumo_pagamentos_dia(self.dia_id)
        resumo_recebimento = database.obter_resumo_pagamentos_dia(dia_recebimento_id)
        self.assertEqual(resumo_original, [])
        self.assertAlmostEqual(resumo_recebimento[0]["total_liquido"], 12.0, places=2)

    def test_fechamento_preserva_fiado_em_aberto_mesmo_apos_quitacao_futura(self):
        p = self.produto(qtd=4, preco=12, custo=5)
        venda_id = database.registrar_venda_completa(
            [self.item(p)], "Dinheiro", 0, "pendente", self.dia_id, cliente_nome="Cliente Teste"
        )
        database.fechar_dia(self.dia_id)
        with database.get_db() as (_, cur):
            snapshot = dict(cur.execute("SELECT * FROM dias_operacao WHERE id=?", (self.dia_id,)).fetchone())
        self.assertAlmostEqual(snapshot["fiado_aberto_fechamento"], 12.0, places=2)
        dia_recebimento_id, abriu = database.abrir_dia()
        self.assertTrue(abriu)
        database.atualizar_status_venda(venda_id, "finalizado", [{"forma_pagamento": "Pix", "valor": 12}])
        with database.get_db() as (_, cur):
            snapshot_depois = dict(cur.execute("SELECT * FROM dias_operacao WHERE id=?", (self.dia_id,)).fetchone())
        self.assertAlmostEqual(snapshot_depois["fiado_aberto_fechamento"], 12.0, places=2)
        venda = next(v for v in database.listar_vendas() if v["id"] == venda_id)
        self.assertEqual(venda["forma_pagamento"], "Fiado")
        self.assertEqual(database.obter_resumo_pagamentos_dia(self.dia_id), [])
        self.assertAlmostEqual(database.obter_resumo_pagamentos_dia(dia_recebimento_id)[0]["total_liquido"], 12.0, places=2)

    def test_backup_consistente_e_valido(self):
        p = self.produto()
        backup_path = criar_backup(self.db_path)
        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).exists())
        # sqlite3.Connection.__exit__ gerencia a transação, mas não fecha o handle.
        # No Windows, TemporaryDirectory não pode remover um DB ainda aberto.
        with closing(sqlite3.connect(backup_path)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT nome FROM produtos WHERE id=?", (p["id"],)).fetchone()[0], p["nome"])

    def test_backup_retries_transient_windows_lock(self):
        """Um lock transitório ao substituir o arquivo deve ser recuperável."""
        self.produto()
        replace_real = os.replace
        chamadas = {"n": 0}

        def replace_com_lock_transitorio(origem, destino):
            chamadas["n"] += 1
            if chamadas["n"] < 3:
                raise PermissionError("lock transitório simulado")
            return replace_real(origem, destino)

        with patch.object(backup_service.os, "replace", side_effect=replace_com_lock_transitorio):
            backup_path = backup_service.criar_backup(self.db_path)

        self.assertIsNotNone(backup_path)
        self.assertTrue(Path(backup_path).is_file())
        self.assertEqual(chamadas["n"], 3)
        with closing(sqlite3.connect(backup_path)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")


class TesteMigracaoLegada(unittest.TestCase):
    def test_migracao_aditiva_preserva_produto_e_garrafa(self):
        with tempfile.TemporaryDirectory(prefix="barns_legacy_") as tempdir:
            path = str(Path(tempdir) / "old.db")
            # Fechamento explícito obrigatório no Windows antes de TemporaryDirectory cleanup.
            with closing(sqlite3.connect(path)) as c:
                c.execute("CREATE TABLE categorias(id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE)")
                c.execute("CREATE TABLE produtos(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, categoria_id INTEGER, quantidade INTEGER DEFAULT 0, preco REAL DEFAULT 0, preco_custo REAL DEFAULT 0, codigo_barras TEXT, estoque_minimo INTEGER DEFAULT 5, estoque_medio INTEGER DEFAULT 15, is_garrafa INTEGER DEFAULT 0, doses_por_garrafa REAL DEFAULT 5.7, preco_dose REAL DEFAULT 0, volume_garrafa_ml INTEGER DEFAULT 900)")
                c.execute("CREATE TABLE garrafas_abertas(id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL, data_abertura TEXT NOT NULL, doses_restantes REAL NOT NULL, perdas_doses REAL DEFAULT 0)")
                c.execute("INSERT INTO produtos(nome,quantidade,preco,preco_custo,is_garrafa,doses_por_garrafa,preco_dose,volume_garrafa_ml) VALUES('Garrafa Antiga',2,90,45,1,5.7,18,900)")
                c.execute("INSERT INTO garrafas_abertas(produto_id,data_abertura,doses_restantes) VALUES(1,'25/09/2026 09:00',1.5)")
                c.commit()
            os.environ["BARNS_DB_PATH"] = path
            try:
                database.criar_tabelas()
                database.criar_tabelas()  # migração idempotente mesmo em reinicializações repetidas
                p = next(x for x in database.buscar_produtos("") if x["nome"] == "Garrafa Antiga")
                self.assertEqual(p["quantidade"], 2)
                bottle = next(x for x in database.obter_garrafas_abertas() if x["produto_id"] == p["id"])
                self.assertAlmostEqual(bottle["doses_restantes"], 1.5, places=2)
                self.assertEqual(bottle["status"], "aberta")
                self.assertAlmostEqual(bottle["doses_iniciais"], 5.7, places=2)
            finally:
                os.environ.pop("BARNS_DB_PATH", None)


class TesteTemaAplicativo(unittest.TestCase):
    def test_paletas_clara_e_escura_usam_o_mesmo_conjunto_de_tokens(self):
        from ui.theme_palette import PALETAS
        self.assertEqual(set(PALETAS["claro"]), set(PALETAS["escuro"]))

    def test_troca_de_tema_mapeia_superficies_texto_e_acento(self):
        from ui.theme_palette import PALETAS, criar_mapa_cores, substituir_cor
        mapa = criar_mapa_cores(PALETAS["claro"], PALETAS["escuro"])
        self.assertEqual(substituir_cor(PALETAS["claro"]["fundo"], mapa), PALETAS["escuro"]["fundo"])
        self.assertEqual(substituir_cor(PALETAS["claro"]["texto"], mapa), PALETAS["escuro"]["texto"])
        self.assertEqual(substituir_cor(PALETAS["claro"]["azul"], mapa), PALETAS["escuro"]["azul"])

    def test_tema_pode_ser_alternado_repetidamente_nos_dois_sentidos(self):
        from ui.theme_palette import PALETAS, criar_mapa_cores, substituir_cor

        # Regressão do erro Windows: nenhuma cor da origem pode representar
        # papéis diferentes com cores de destino diferentes.
        for origem, destino in (("claro", "escuro"), ("escuro", "claro")):
            mapa = criar_mapa_cores(PALETAS[origem], PALETAS[destino])
            for token, cor_origem in PALETAS[origem].items():
                self.assertEqual(
                    substituir_cor(cor_origem, mapa),
                    PALETAS[destino][token],
                    f"Falha ao mapear {token}: {origem} -> {destino}",
                )

    def test_cores_compartilhadas_so_sao_permitidas_com_destinos_compativeis(self):
        from ui.theme_palette import PALETAS, criar_mapa_cores

        for origem, destino in (("claro", "escuro"), ("escuro", "claro")):
            # construir o mapa deve concluir sem ValueError de ambiguidade.
            self.assertTrue(criar_mapa_cores(PALETAS[origem], PALETAS[destino]))

    def test_troca_de_tema_mapeia_cores_dentro_de_tuplas(self):
        from ui.theme_palette import PALETAS, criar_mapa_cores, substituir_cor
        mapa = criar_mapa_cores(PALETAS["claro"], PALETAS["escuro"])
        atual = (PALETAS["claro"]["card"], PALETAS["claro"]["texto"])
        esperado = (PALETAS["escuro"]["card"], PALETAS["escuro"]["texto"])
        self.assertEqual(substituir_cor(atual, mapa), esperado)

    def test_preferencia_de_tema_persiste_sem_apagar_outras_configuracoes(self):
        import json
        from pathlib import Path
        from ui.theme_preferences import carregar_modo_tema, salvar_modo_tema
        with tempfile.TemporaryDirectory(prefix="barns_theme_") as tempdir:
            arquivo = Path(tempdir) / "settings.json"
            arquivo.write_text(json.dumps({"geometria": "maximizada"}), encoding="utf-8")
            salvar_modo_tema("escuro", arquivo)
            self.assertEqual(carregar_modo_tema(arquivo), "escuro")
            self.assertEqual(json.loads(arquivo.read_text(encoding="utf-8"))["geometria"], "maximizada")

    def test_preferencia_invalida_volta_para_tema_claro(self):
        from pathlib import Path
        from ui.theme_preferences import carregar_modo_tema
        with tempfile.TemporaryDirectory(prefix="barns_theme_invalid_") as tempdir:
            arquivo = Path(tempdir) / "settings.json"
            arquivo.write_text('{"modo_tema":"neon"}', encoding="utf-8")
            self.assertEqual(carregar_modo_tema(arquivo), "claro")

class TesteTokensSemanticosTema(unittest.TestCase):
    def test_textos_sobre_marca_e_alerta_trocam_sem_colisoes(self):
        from ui.theme_palette import PALETAS, criar_mapa_cores, substituir_cor
        for origem, destino in (("claro", "escuro"), ("escuro", "claro")):
            mapa = criar_mapa_cores(PALETAS[origem], PALETAS[destino])
            for token in ("texto_sobre_marca", "texto_sobre_alerta"):
                self.assertEqual(
                    substituir_cor(PALETAS[origem][token], mapa),
                    PALETAS[destino][token],
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
