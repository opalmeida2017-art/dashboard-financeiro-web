"""Tabelas e colunas do BIWEB que não existem no dump SATI (schema c3332).

Revision ID: 6
Revises: 5
Create Date: 2026-05-29

Cria no schema public:
- apartamentos, usuarios, static_expense_groups, configuracoes_robo, notificacoes
- tb_logs_robo, tb_user_activity
- despesas_viagem_associadas, despesas_viagem_excluidas
- coluna incluir_em_tipo_d em static_expense_groups

Não recria relFil* (dados vêm do SATI via sati_queries quando USE_SATI_SOURCE=true).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6"
down_revision: Union[str, Sequence[str], None] = "5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  print("--- Tabelas de sistema BIWEB (public) para uso com banco SATI ---")

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS apartamentos (
        id SERIAL PRIMARY KEY,
        nome_empresa TEXT NOT NULL,
        slug TEXT UNIQUE,
        status TEXT DEFAULT 'ativo',
        data_criacao TEXT NOT NULL,
        data_vencimento TEXT,
        notas_admin TEXT,
        logo_filename TEXT
    );
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        nome TEXT,
        role TEXT DEFAULT 'usuario'
    );
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS static_expense_groups (
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        group_name TEXT NOT NULL,
        is_despesa TEXT DEFAULT 'S',
        is_custo_viagem TEXT DEFAULT 'N',
        PRIMARY KEY (apartamento_id, group_name)
    );
    """
  )

  op.execute(
    """
    ALTER TABLE static_expense_groups
    ADD COLUMN IF NOT EXISTS incluir_em_tipo_d BOOLEAN DEFAULT FALSE;
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS configuracoes_robo (
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        chave TEXT NOT NULL,
        valor TEXT,
        PRIMARY KEY (apartamento_id, chave)
    );
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS notificacoes (
        id SERIAL PRIMARY KEY,
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        mensagem TEXT NOT NULL,
        lida BOOLEAN DEFAULT FALSE,
        timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS tb_logs_robo (
        id SERIAL PRIMARY KEY,
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        mensagem TEXT
    );
    """
  )

  op.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_tb_logs_robo_apt_ts
        ON tb_logs_robo (apartamento_id, timestamp DESC);
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS tb_user_activity (
        apartamento_id INTEGER PRIMARY KEY REFERENCES apartamentos(id),
        last_seen_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS despesas_viagem_associadas (
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        numero INTEGER NOT NULL,
        coditemnota INTEGER NOT NULL,
        PRIMARY KEY (apartamento_id, numero, coditemnota)
    );
    """
  )

  op.execute(
    """
    CREATE TABLE IF NOT EXISTS despesas_viagem_excluidas (
        apartamento_id INTEGER NOT NULL REFERENCES apartamentos(id),
        numero INTEGER NOT NULL,
        coditemnota INTEGER NOT NULL,
        PRIMARY KEY (apartamento_id, numero, coditemnota)
    );
    """
  )

  print("--- Tabelas de sistema BIWEB criadas/verificadas ---")


def downgrade() -> None:
  op.execute("DROP TABLE IF EXISTS despesas_viagem_excluidas CASCADE;")
  op.execute("DROP TABLE IF EXISTS despesas_viagem_associadas CASCADE;")
  op.execute("DROP TABLE IF EXISTS tb_user_activity CASCADE;")
  op.execute("DROP TABLE IF EXISTS tb_logs_robo CASCADE;")
  op.execute("DROP TABLE IF EXISTS notificacoes CASCADE;")
  op.execute("DROP TABLE IF EXISTS configuracoes_robo CASCADE;")
  op.execute("DROP TABLE IF EXISTS static_expense_groups CASCADE;")
  op.execute("DROP TABLE IF EXISTS usuarios CASCADE;")
  op.execute("DROP TABLE IF EXISTS apartamentos CASCADE;")
