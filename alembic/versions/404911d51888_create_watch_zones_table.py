"""create watch_zones table

Revision ID: 404911d51888
Revises: 97f89c6b3c43
Create Date: 2026-11-05 12:30:03.145418

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '404911d51888'
down_revision: Union[str, Sequence[str], None] = '97f89c6b3c43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_zones",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("radius_km", sa.Float, nullable=False),
        sa.Column("min_magnitude", sa.Float, nullable=False, server_default="0"),
        sa.Column("webhook_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("radius_km > 0 AND radius_km <= 2000", name="ck_watch_zones_radius"),
    )
    op.execute("ALTER TABLE watch_zones ADD COLUMN center geography(Point, 4326) NOT NULL")
    op.execute("CREATE INDEX ix_watch_zones_center ON watch_zones USING GIST (center)")


def downgrade() -> None:
    op.drop_table("watch_zones")
