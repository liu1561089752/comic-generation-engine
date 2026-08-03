"""extend layout_shots.shot_id length to 50

Revision ID: bf5803f56b85
Revises: f059c9246c6d
Create Date: 2026-07-28 17:27:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf5803f56b85'
down_revision: Union[str, None] = 'f059c9246c6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'layout_shots', 'shot_id',
        type_=sa.String(50),
        existing_type=sa.String(10),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'layout_shots', 'shot_id',
        type_=sa.String(10),
        existing_type=sa.String(50),
        nullable=False,
    )
