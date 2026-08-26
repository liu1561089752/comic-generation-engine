"""add stream_output to tasks for streaming task output

Revision ID: d7e8f9a0b1c2
Revises: c1a2b3c4d5e6
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """tasks 表新增 stream_output 列（流式任务输出的实时文本）。"""
    op.add_column(
        "tasks",
        sa.Column("stream_output", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("tasks", "stream_output")
