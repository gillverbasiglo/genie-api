"""Add private_chat_messages table

Revision ID: e55cc7ce8809
Revises: 4038d2c387ec
Create Date: 2025-05-21 21:02:44.977747

"""
import enum
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e55cc7ce8809'
down_revision: Union[str, None] = '4038d2c387ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class MessageStatusEnum(str, enum.Enum):
    SENT = "SENT"         # Message has been sent but not yet delivered
    DELIVERED = "DELIVERED"  # Message has been delivered to recipient
    READ = "READ"         # Message has been read by recipient

class MessageTypeEnum(str, enum.Enum):
    TEXT = "TEXT"     # Plain text messages
    IMAGE = "IMAGE"   # Image attachments
    VIDEO = "VIDEO"   # Video attachments
    FILE = "FILE"     # Generic file attachments
    AUDIO = "AUDIO"   # Audio attachments

# Create PostgreSQL ENUM types for message status and type
message_status_enum = postgresql.ENUM(*[e.value for e in MessageStatusEnum], name="messagestatus", create_type=False)
message_type_enum = postgresql.ENUM(*[e.value for e in MessageTypeEnum], name="messagetype", create_type=False)

def upgrade() -> None:
    """Upgrade database schema by creating new table and ENUM types.
    
    This function:
    1. Creates PostgreSQL ENUM types for message status and type
    2. Creates the private_chat_messages table with all necessary columns
    """
    # Create ENUM types in the database
    message_type_enum.create(op.get_bind(), checkfirst=True)

    # Create private_chat_messages table with the following columns:
    # - id: Unique identifier for each message
    # - sender_id: Foreign key to users table (sender)
    # - receiver_id: Foreign key to users table (recipient)
    # - message_type: Type of message (text, image, etc.)
    # - content: Text content for text messages
    # - media_url: URL for media attachments
    # - metadata: Additional JSON metadata for the message
    # - status: Current delivery status of the message
    # - created_at: Timestamp of message creation
    # - updated_at: Timestamp of last update
    op.create_table(
        'private_chat_messages',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('sender_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('receiver_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('message_type', message_type_enum, nullable=False, server_default="TEXT"),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', message_status_enum, nullable=False, server_default="SENT"),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema by removing the table and ENUM types.
    
    This function:
    1. Drops the private_chat_messages table
    2. Removes the PostgreSQL ENUM types
    """
    op.drop_table('private_chat_messages')
    message_status_enum.drop(op.get_bind(), checkfirst=True)
    message_type_enum.drop(op.get_bind(), checkfirst=True)
