"""add language to users

Revision ID: a1b2c3d4e5f6
Revises: <предыдущий revision id>
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = None  # <-- замени на актуальный revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('language', sa.String(5), server_default='ru', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'language')
