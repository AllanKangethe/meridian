"""add eonet columns to events

Revision ID: c9eec4d46f16
Revises: 404911d51888
Create Date: 2026-11-13 23:50:42.255617

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9eec4d46f16'
down_revision: Union[str, Sequence[str], None] = '404911d51888'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("magnitude_unit", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "magnitude_unit")

