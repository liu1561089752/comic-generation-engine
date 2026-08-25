"""add unique constraint: one novel / one world per project

Revision ID: c1a2b3c4d5e6
Revises: bf5803f56b85
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, None] = 'bf5803f56b85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 每个项目只允许一本小说 / 一个世界观（服务层已校验，数据库层兜底）
    op.create_index(
        'uq_novels_one_per_project', 'novels', ['project_id'], unique=True
    )
    op.create_index(
        'uq_world_buildings_one_per_project', 'world_buildings', ['project_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index('uq_world_buildings_one_per_project', table_name='world_buildings')
    op.drop_index('uq_novels_one_per_project', table_name='novels')
