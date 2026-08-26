"""relax active-task dedup index for single image generation tasks

Revision ID: e1f2a3b4c5d6
Revises: d7e8f9a0b1c2
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 单图生成任务类型：每张图独立任务，同类型可多任务排队（并发由信号量控制），
# 因此从"同项目同类型唯一活跃"的去重索引中排除。
_IMAGE_TASK_TYPES = (
    "'generate_character_image', 'generate_state_image', "
    "'generate_scene_image', 'generate_prop_image', "
    "'generate_building_image', 'generate_outfit_image'"
)


def upgrade() -> None:
    op.drop_index("uq_tasks_active_dedup", table_name="tasks")
    op.create_index(
        "uq_tasks_active_dedup",
        "tasks",
        ["project_id", "task_type"],
        unique=True,
        postgresql_where=text(
            "status IN ('queued', 'running') "
            f"AND task_type NOT IN ({_IMAGE_TASK_TYPES})"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_tasks_active_dedup", table_name="tasks")
    op.create_index(
        "uq_tasks_active_dedup",
        "tasks",
        ["project_id", "task_type"],
        unique=True,
        postgresql_where=text("status IN ('queued', 'running')"),
    )
