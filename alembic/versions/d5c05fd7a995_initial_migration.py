"""initial migration

Revision ID: d5c05fd7a995
Revises:
Create Date: 2026-03-09 22:30:15.190342

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5c05fd7a995"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("genre", sa.String(), nullable=False),
        sa.Column("target_chapters", sa.Integer(), nullable=False),
        sa.Column("basic_idea", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("memory_summary", sa.Text(), nullable=True),
        sa.Column("current_chapter", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_books_id"), "books", ["id"], unique=False)

    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["book_id"],
            ["books.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chapters_id"), "chapters", ["id"], unique=False)

    op.create_table(
        "global_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deepseek_api_key", sa.String(), nullable=True),
        sa.Column("deepseek_base_url", sa.String(), nullable=True),
        sa.Column("default_model", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("global_config")
    op.drop_index(op.f("ix_chapters_id"), table_name="chapters")
    op.drop_table("chapters")
    op.drop_index(op.f("ix_books_id"), table_name="books")
    op.drop_table("books")
