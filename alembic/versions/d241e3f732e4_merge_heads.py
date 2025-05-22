"""Merge heads

Revision ID: d241e3f732e4
Revises: c345850e424c, eef763a7148e
Create Date: 2025-05-22 12:00:40.748202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd241e3f732e4'
down_revision: Union[str, None] = ('c345850e424c', 'eef763a7148e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
