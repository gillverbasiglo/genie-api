"""Add LLM chat session and message tables

Revision ID: 58c708d15df6
Revises: 9d80d8662b2d
Create Date: 2025-06-18 23:56:44.378080

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58c708d15df6'
down_revision: Union[str, None] = '9d80d8662b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_chat_sessions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(), nullable=True, default='New Chat'),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'llm_chat_messages',
        sa.Column('id', sa.String(), primary_key=True, default=uuid.uuid4),
        sa.Column('session_id', sa.String(), sa.ForeignKey('llm_chat_sessions.id'), nullable=False),
        sa.Column('sender', sa.Enum('user', 'llm', name='sender'), nullable=False),
        sa.Column('content', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('llm_chat_messages')
    op.drop_table('llm_chat_sessions')
    op.execute('DROP TYPE sender')
