"""Add is_from_genie column to private_chat_messages

Revision ID: 4b2a540804a8
Revises: 408deb13f588
Create Date: 2025-07-08 11:33:55.857672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4b2a540804a8'
down_revision: Union[str, None] = '408deb13f588'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('private_chat_messages',
        sa.Column('is_from_genie', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column('private_chat_messages', 'is_from_genie', server_default=None)


def downgrade() -> None:
    op.drop_column('private_chat_messages', 'is_from_genie')
    