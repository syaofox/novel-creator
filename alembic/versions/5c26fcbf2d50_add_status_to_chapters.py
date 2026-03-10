"""add status to chapters

Revision ID: 5c26fcbf2d50
Revises: 37593cd8ced1
Create Date: 2026-03-10 17:27:08.101749

"""

from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5c26fcbf2d50"
down_revision: str | None = "37593cd8ced1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chapters", sa.Column("status", sa.String(), nullable=True))
    op.execute("UPDATE chapters SET status = '未完成' WHERE status IS NULL")


def downgrade() -> None:
    op.drop_column("chapters", "status")
