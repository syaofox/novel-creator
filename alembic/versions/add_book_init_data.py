"""add book_init_data table

Revision ID: add_book_init_data
Revises: 2f4356b0ee6c
Create Date: 2026-03-13 00:00:00.000000

"""

from typing import Union
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "add_book_init_data"
down_revision: str | Sequence[str] | None = "2f4356b0ee6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "book_init_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True, default=""),
        sa.Column("book_title", sa.String(), nullable=True, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("book_init_data")
