"""add style column to books

Revision ID: 37593cd8ced1
Revises: 5a2431f8df98
Create Date: 2026-03-10 15:43:11.277245

"""

from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "37593cd8ced1"
down_revision: str | None = "5a2431f8df98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("books", sa.Column("style", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "style")
