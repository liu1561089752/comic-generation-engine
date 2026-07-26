"""align schema with orm models

Revision ID: b3d7a1e5c8f2
Revises: 9e3b1c7d2f4a
Create Date: 2026-07-26 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d7a1e5c8f2'
down_revision: Union[str, None] = '9e3b1c7d2f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 部分历史开发库是用 Base.metadata.create_all() 建的表，列/索引可能已按模型存在，
# 因此这里先反射再决定是否执行；离线模式(--sql)拿不到连接，反射结果为 None，
# 此时一律照常输出 DDL，由人工核对。
def _column_names(table_name: str):
    if context.is_offline_mode():
        return None
    return {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str):
    if context.is_offline_mode():
        return None
    return {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _should_create(existing, target: str) -> bool:
    """目标尚不存在（或无法判定）时才创建"""
    return existing is None or target not in existing


def _should_modify(existing, target: str) -> bool:
    """目标确实存在（或无法判定）时才改动"""
    return existing is None or target in existing


def upgrade() -> None:
    # ---- 1. characters: 补齐 app/models/character.py 声明但初始 schema 缺失的两列 ----
    character_columns = _column_names('characters')
    if _should_create(character_columns, 'aliases'):
        op.add_column('characters', sa.Column('aliases', sa.Text(), nullable=True))
    if _should_create(character_columns, 'description'):
        op.add_column('characters', sa.Column('description', sa.Text(), nullable=True))
    # characters.config 是初始 schema 的遗留列，模型已不再声明。
    # 它在 f059c9246c6d 里本来就是 nullable=True，不会阻塞 ORM 插入，
    # 故保留原样不 drop，避免丢历史数据。

    # ---- 2. layout_pages: 这四列的数据已拆到 image_prompts / generated_images /
    #        reference_matches / layout_shots 表，ORM 不再提供取值，必须放宽 NOT NULL ----
    layout_page_columns = _column_names('layout_pages')
    if _should_modify(layout_page_columns, 'image_prompt'):
        op.alter_column('layout_pages', 'image_prompt',
                        existing_type=sa.Text(), nullable=True)
    if _should_modify(layout_page_columns, 'image_url'):
        op.alter_column('layout_pages', 'image_url',
                        existing_type=sa.String(length=500), nullable=True)
    if _should_modify(layout_page_columns, 'reference_ids'):
        op.alter_column('layout_pages', 'reference_ids',
                        existing_type=sa.JSON(), nullable=True)
    if _should_modify(layout_page_columns, 'shots'):
        op.alter_column('layout_pages', 'shots',
                        existing_type=sa.JSON(), nullable=True)

    # ---- 3. style_templates.width: Integer -> String(20)，对齐 app/models/world.py ----
    op.alter_column('style_templates', 'width',
                    existing_type=sa.Integer(),
                    type_=sa.String(length=20),
                    existing_nullable=True,
                    postgresql_using='width::varchar')

    # ---- 4. projects.user_id ----
    # 模型是 UUID + ForeignKey(users.id) + NOT NULL，迁移 9e3b1c7d2f4a 建的是
    # String(100) NULL 且无外键。本次【不动】它：库里可能存在 user_id 为 NULL 或
    # 非 UUID 文本的历史行，直接改类型/加 NOT NULL 会让整个迁移失败。
    # 需先人工回填归属再单独出一版收紧迁移，回填 SQL 见交付说明。

    # ---- 5. tasks: 活跃任务去重的部分唯一索引（I4）----
    # 唯一索引建立前必须清掉库中已存在的重复活跃任务，否则 CREATE UNIQUE INDEX 直接报错。
    # 只处理三列全非 NULL 的行：PostgreSQL 唯一索引中 NULL 互不冲突，
    # project_id 或 novel_id 为 NULL 的行本来就不会触发冲突，不应被误判为重复。
    # 同组内保留 created_at 最新的一条，其余置为 failed。
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY project_id, task_type, (input_data->>'novel_id')
                       ORDER BY created_at DESC NULLS LAST, id DESC
                   ) AS rn
            FROM tasks
            WHERE status IN ('queued', 'running')
              AND project_id IS NOT NULL
              AND input_data->>'novel_id' IS NOT NULL
        )
        UPDATE tasks
        SET status = 'failed',
            error_message = COALESCE(tasks.error_message, '')
                            || '[migration b3d7a1e5c8f2] 与同项目同类型的活跃任务重复，已置为 failed',
            completed_at = COALESCE(tasks.completed_at, now())
        FROM ranked
        WHERE tasks.id = ranked.id
          AND ranked.rn > 1
    """))

    if _should_create(_index_names('tasks'), 'uq_tasks_active_dedup'):
        op.create_index(
            'uq_tasks_active_dedup',
            'tasks',
            ['project_id', 'task_type', sa.text("(input_data->>'novel_id')")],
            unique=True,
            postgresql_where=sa.text("status IN ('queued','running')"),
        )


def downgrade() -> None:
    # ---- 5. 去重索引 ----
    # 被置为 failed 的重复任务无法还原（原状态已丢失），这一步不可逆。
    if _should_modify(_index_names('tasks'), 'uq_tasks_active_dedup'):
        op.drop_index('uq_tasks_active_dedup', table_name='tasks')

    # ---- 3. style_templates.width: String(20) -> Integer ----
    # 剥掉非数字字符再转，避免 "1080px" 之类的值让回滚失败；剥完为空则写 NULL。
    op.alter_column('style_templates', 'width',
                    existing_type=sa.String(length=20),
                    type_=sa.Integer(),
                    existing_nullable=True,
                    postgresql_using="NULLIF(regexp_replace(COALESCE(width, ''), '[^0-9]', '', 'g'), '')::integer")

    # ---- 2. layout_pages: 恢复 NOT NULL 前必须先补齐 NULL 值，否则加约束会失败 ----
    layout_page_columns = _column_names('layout_pages')
    if _should_modify(layout_page_columns, 'image_prompt'):
        op.execute("UPDATE layout_pages SET image_prompt = '' WHERE image_prompt IS NULL")
        op.alter_column('layout_pages', 'image_prompt',
                        existing_type=sa.Text(), nullable=False)
    if _should_modify(layout_page_columns, 'image_url'):
        op.execute("UPDATE layout_pages SET image_url = '' WHERE image_url IS NULL")
        op.alter_column('layout_pages', 'image_url',
                        existing_type=sa.String(length=500), nullable=False)
    if _should_modify(layout_page_columns, 'reference_ids'):
        op.execute("UPDATE layout_pages SET reference_ids = '[]'::json WHERE reference_ids IS NULL")
        op.alter_column('layout_pages', 'reference_ids',
                        existing_type=sa.JSON(), nullable=False)
    if _should_modify(layout_page_columns, 'shots'):
        op.execute("UPDATE layout_pages SET shots = '[]'::json WHERE shots IS NULL")
        op.alter_column('layout_pages', 'shots',
                        existing_type=sa.JSON(), nullable=False)

    # ---- 1. characters: 回滚会连带丢掉 aliases / description 已写入的数据 ----
    character_columns = _column_names('characters')
    if _should_modify(character_columns, 'description'):
        op.drop_column('characters', 'description')
    if _should_modify(character_columns, 'aliases'):
        op.drop_column('characters', 'aliases')
