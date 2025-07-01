"""Change content column to Text in llm_chat_messages

Revision ID: 408deb13f588
Revises: 58c708d15df6
Create Date: 2025-07-01 16:25:05.462449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '408deb13f588'
down_revision: Union[str, None] = '58c708d15df6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'llm_chat_messages',
        'content',
        type_=sa.Text(),
        postgresql_using='content::text',
        existing_type=sa.dialects.postgresql.JSONB(),
    )


def downgrade() -> None:
    op.alter_column(
        'llm_chat_messages',
        'content',
        type_=sa.dialects.postgresql.JSONB(),
        postgresql_using='content::jsonb',
        existing_type=sa.Text(),
    )
