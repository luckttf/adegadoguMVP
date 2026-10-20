"""Fachada de compatibilidade para o legado; implementações vivem nos módulos internos.

Os imports abaixo são reexportações intencionais para não quebrar chamadas existentes.
"""
from infrastructure.database.connection import remover_acentos, obter_caminho_banco, conectar, get_db
from infrastructure.database.schema import criar_tabelas, popular_exemplos
from domain.bottle_rules import calcular_doses_estimadas, VOLUME_GARRAFA_ML_PADRAO, VOLUME_DOSE_ML_PADRAO, FATOR_PERDA_PADRAO
from infrastructure.database.repositories.operations import *
from infrastructure.database.repositories.catalog import *
from infrastructure.database.repositories.bottles import *
from infrastructure.database.repositories.sales import *
