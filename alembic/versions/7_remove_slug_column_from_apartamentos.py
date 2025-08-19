"""remove slug column from apartamentos

Revision ID: 7
Revises: 6
Create Date: 2025-08-19 00:22:21.539924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7'
down_revision: Union[str, Sequence[str], None] = '6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op
import sqlalchemy as sa

def upgrade():
    op.drop_column('apartamentos', 'slug')

def downgrade():
    op.add_column('apartamentos', sa.Column('slug', sa.Text(), nullable=True))