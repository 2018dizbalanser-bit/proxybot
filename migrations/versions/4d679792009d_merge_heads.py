"""merge_heads

Revision ID: 4d679792009d
Revises: 1faa70df3608, a1b2c3d4e5f6
Create Date: 2026-04-14 10:20:08.626132

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d679792009d'
down_revision: Union[str, Sequence[str], None] = ('1faa70df3608', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
