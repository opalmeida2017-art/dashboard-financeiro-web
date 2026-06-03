"""Adiciona coluna logo_filename em apartamentos.

Revision ID: 7
Revises: 6
Create Date: 2026-06-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "7"
down_revision: Union[str, Sequence[str], None] = "6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE apartamentos
        ADD COLUMN IF NOT EXISTS logo_filename TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE apartamentos
        DROP COLUMN IF EXISTS logo_filename;
        """
    )
