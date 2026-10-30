"""create events table

Revision ID: 97f89c6b3c43
Revises: 
Create Date: 2026-10-30 00:59:46.102830

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '97f89c6b3c43'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("source_event_id", sa.Text, nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("magnitude", sa.Float, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw", postgresql.JSONB, nullable=False),
        sa.UniqueConstraint("source", "source_event_id", name="uq_events_source_event"),
    )

    op.execute("ALTER TABLE events ADD COLUMN location geography(Point, 4326) NOT NULL")
    op.execute("CREATE INDEX ix_events_location ON events USING GIST (location)")
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])


def downgrade() -> None:
    op.drop_table("events")