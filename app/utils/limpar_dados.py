"""Limpeza de dados importados por apartamento."""

from __future__ import annotations

import shutil

from sqlalchemy import text

from app import config
from app.data.db_connection import engine
from app.utils.paths import downloads_dir


def limpar_pasta_downloads(apartamento_id: int) -> None:
    pasta_downloads = downloads_dir(apartamento_id)
    if pasta_downloads.exists():
        print(f"-> Removendo pasta de downloads temporária: {pasta_downloads}")
        try:
            shutil.rmtree(pasta_downloads)
            print("-> Pasta removida com sucesso.")
        except Exception as e:
            print(f"Aviso: Não foi possível remover a pasta. Erro: {e}")
    else:
        print("-> Aviso: Pasta de downloads não encontrada.")


def limpar_dados_importados(apartamento_id: int) -> None:
    tabelas_importadas = [info["table"] for info in config.EXCEL_FILES_CONFIG.values()]
    tabelas_dependentes = ["static_expense_groups", "tb_logs_robo"]
    tabelas_para_limpar = tabelas_importadas + tabelas_dependentes

    print(f"\nAs seguintes tabelas serão limpas para o apartamento ID {apartamento_id}:")
    for tabela in tabelas_para_limpar:
        print(f"- {tabela}")

    try:
        with engine.connect() as conn:
            with conn.begin():
                print("\nIniciando a limpeza dos dados...")
                for tabela in tabelas_para_limpar:
                    try:
                        query = text(f'DELETE FROM "{tabela}" WHERE apartamento_id = :apt_id')
                        result = conn.execute(query, {"apt_id": apartamento_id})
                        print(f"-> {result.rowcount} registros removidos de '{tabela}'.")
                    except Exception as e:
                        print(f"Aviso: Não foi possível limpar a tabela '{tabela}'. Erro: {e}")

            print("\nLimpeza de dados no banco de dados concluída com sucesso!")

        limpar_pasta_downloads(apartamento_id)

    except Exception as e:
        print(f"\nOcorreu um erro crítico durante a operação. Nenhuma alteração foi salva. Erro: {e}")
