"""Rename metadata to message_meta in private_chat_messages

Revision ID: c345850e424c
Revises: e55cc7ce8809
Create Date: 2025-05-21 21:16:11.876449

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c345850e424c'
down_revision: Union[str, None] = 'e55cc7ce8809'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename column `metadata` to `message_meta`
    op.alter_column(
        'private_chat_messages',
        'metadata',
        new_column_name='message_meta'
    )


def downgrade() -> None:
    # Revert column name back to `metadata`
    op.alter_column(
        'private_chat_messages',
        'message_meta',
        new_column_name='metadata'
    )
