"""Snapshot BI — viagens com DRE pré-calculado (schema public, sobrevive ao restore SATI).

Revision ID: 8
Revises: 7
Create Date: 2026-06-22
"""

from typing import Sequence, Union

from alembic import op


revision: str = "8"
down_revision: Union[str, Sequence[str], None] = "7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bi_snapshot_meta (
            apartamento_id INTEGER PRIMARY KEY,
            sati_generation TEXT,
            status TEXT NOT NULL DEFAULT 'empty',
            row_count INTEGER DEFAULT 0,
            build_started_at TIMESTAMP,
            rebuilt_at TIMESTAMP,
            error_message TEXT
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bi_viagem_dre (
            apartamento_id INTEGER NOT NULL,
            numero INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            dataviagemmotorista TIMESTAMP,
            placaveiculo TEXT,
            nomefilial TEXT,
            codembarcador INTEGER,
            veiculoproprio TEXT,
            tipofrete TEXT,
            nomeunidembarque TEXT,
            PRIMARY KEY (apartamento_id, numero)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bi_viagem_dre_apt_data
        ON bi_viagem_dre (apartamento_id, dataviagemmotorista);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bi_viagem_dre;")
    op.execute("DROP TABLE IF EXISTS bi_snapshot_meta;")
