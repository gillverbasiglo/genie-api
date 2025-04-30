"""Add message tables

Revision ID: 93fad7f87d2c
Revises: 5d142413ab4b
Create Date: 2025-04-30 12:58:26.213043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93fad7f87d2c'
down_revision: Union[str, None] = '5d142413ab4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'private_chat_messages',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('sender_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('receiver_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('sent', 'delivered', 'read', name='messagestatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

def downgrade() -> None:
    op.drop_table('private_chat_messages')
    op.execute('DROP TYPE messagestatus')
