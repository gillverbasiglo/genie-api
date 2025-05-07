"""empty message

Revision ID: a072d5284147
Revises: 58258a79f194, 9602979b5113
Create Date: 2025-05-07 14:39:31.838215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a072d5284147'
down_revision: Union[str, None] = ('58258a79f194', '9602979b5113')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
