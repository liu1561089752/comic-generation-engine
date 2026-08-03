"""initial schema - 完全匹配 ORM 模型

重写初始迁移，一次性创建所有表，字段完全匹配 app/models/ 下的 ORM 定义。
删除了所有 T9 遗留表（panels/bubbles/prompts/shots/images/pages/scenes/character_expressions），
补建了之前遗漏的表（character_states/layout_shots/image_prompts/reference_matches/generated_images/prompt_modules）。

Revision ID: f059c9246c6d
Revises:
Create Date: 2026-07-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f059c9246c6d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ====== 1. 无外键依赖的表 ======
    op.create_table('users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_admin', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )

    op.create_table('llm_config',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('api_base', sa.String(length=500), nullable=True),
        sa.Column('api_key', sa.String(length=500), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('image_gen_config',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('api_base', sa.String(length=500), nullable=True),
        sa.Column('api_key', sa.String(length=500), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('plugins',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('plugin_type', sa.String(length=50), nullable=False),
        sa.Column('config_schema', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # ====== 2. 依赖 users 的表 ======
    op.create_table('projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('project_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('cover_image_url', sa.String(length=500), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_user_id'), 'projects', ['user_id'], unique=False)

    op.create_table('notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('related_url', sa.String(length=500), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('system_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.UUID(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # ====== 3. prompt_templates / prompt_modules ======
    op.create_table('prompt_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cover_image_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prompt_templates_is_active'), 'prompt_templates', ['is_active'], unique=False)

    op.create_table('prompt_modules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('template_id', sa.UUID(), nullable=False),
        sa.Column('module_key', sa.String(length=50), nullable=False),
        sa.Column('module_label', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id', 'module_key', name='uq_prompt_modules_template_module')
    )
    op.create_index(op.f('ix_prompt_modules_template_id'), 'prompt_modules', ['template_id'], unique=False)

    # ====== 4. novels → characters → character_states/outfits/reference_images/relations ======
    op.create_table('novels',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('author', sa.String(length=100), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('cleaned_text', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('format', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_novels_project_id'), 'novels', ['project_id'], unique=False)

    op.create_table('characters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('aliases', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('role_type', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('stable_key', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_characters_project_id'), 'characters', ['project_id'], unique=False)
    op.create_index(op.f('ix_characters_stable_key'), 'characters', ['stable_key'], unique=False)
    op.create_index(op.f('ix_characters_name'), 'characters', ['name'], unique=False)
    op.create_index(op.f('ix_characters_role_type'), 'characters', ['role_type'], unique=False)

    op.create_table('character_states',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('character_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('aliases', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_character_states_character_id'), 'character_states', ['character_id'], unique=False)

    op.create_table('character_outfits',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('character_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('outfit_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color_scheme', sa.JSON(), nullable=True),
        sa.Column('scene_tags', sa.JSON(), nullable=True),
        sa.Column('reference_image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_character_outfits_character_id'), 'character_outfits', ['character_id'], unique=False)

    op.create_table('character_reference_images',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('character_id', sa.UUID(), nullable=False),
        sa.Column('state_id', sa.UUID(), nullable=True),
        sa.Column('angle', sa.String(length=20), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['character_id'], ['characters.id']),
        sa.ForeignKeyConstraint(['state_id'], ['character_states.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_character_reference_images_character_id'), 'character_reference_images', ['character_id'], unique=False)
    op.create_index(op.f('ix_character_reference_images_state_id'), 'character_reference_images', ['state_id'], unique=False)

    op.create_table('character_relations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('character_a_id', sa.UUID(), nullable=False),
        sa.Column('character_b_id', sa.UUID(), nullable=False),
        sa.Column('relation_type_a_to_b', sa.String(length=50), nullable=False),
        sa.Column('relation_type_b_to_a', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['character_a_id'], ['characters.id']),
        sa.ForeignKeyConstraint(['character_b_id'], ['characters.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_character_relations_project_id'), 'character_relations', ['project_id'], unique=False)
    op.create_index(op.f('ix_character_relations_character_a_id'), 'character_relations', ['character_a_id'], unique=False)
    op.create_index(op.f('ix_character_relations_character_b_id'), 'character_relations', ['character_b_id'], unique=False)

    # ====== 5. chapters / paragraphs / editor_versions ======
    op.create_table('chapters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('novel_id', sa.UUID(), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chapters_novel_id'), 'chapters', ['novel_id'], unique=False)
    op.create_index(op.f('ix_chapters_status'), 'chapters', ['status'], unique=False)

    op.create_table('paragraphs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chapter_id', sa.UUID(), nullable=False),
        sa.Column('paragraph_number', sa.String(length=10), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('annotation_type', sa.String(length=20), nullable=True),
        sa.Column('annotation_content', sa.Text(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_paragraphs_chapter_id'), 'paragraphs', ['chapter_id'], unique=False)

    op.create_table('editor_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chapter_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=True),
        sa.Column('content_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_editor_versions_chapter_id'), 'editor_versions', ['chapter_id'], unique=False)

    # ====== 6. script_chapters / script_shots ======
    op.create_table('script_chapters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('novel_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_script_chapters_novel_id'), 'script_chapters', ['novel_id'], unique=False)

    op.create_table('script_shots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chapter_id', sa.UUID(), nullable=False),
        sa.Column('shot_id', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['script_chapters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_script_shots_chapter_id'), 'script_shots', ['chapter_id'], unique=False)

    # ====== 7. storyboard_chapters / storyboard_shots ======
    op.create_table('storyboard_chapters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('novel_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_storyboard_chapters_novel_id'), 'storyboard_chapters', ['novel_id'], unique=False)

    op.create_table('storyboard_shots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chapter_id', sa.UUID(), nullable=False),
        sa.Column('shot_id', sa.String(length=10), nullable=False),
        sa.Column('storyboard_details', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['storyboard_chapters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_storyboard_shots_chapter_id'), 'storyboard_shots', ['chapter_id'], unique=False)

    # ====== 8. layout_chapters / layout_pages / layout_shots / image_prompts / reference_matches / generated_images ======
    op.create_table('layout_chapters',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('novel_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['novel_id'], ['novels.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_layout_chapters_novel_id'), 'layout_chapters', ['novel_id'], unique=False)

    op.create_table('layout_pages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chapter_id', sa.UUID(), nullable=False),
        sa.Column('page_id', sa.String(length=10), nullable=False),
        sa.Column('layout_type', sa.String(length=50), nullable=False),
        sa.Column('page_purpose', sa.Text(), nullable=False),
        sa.Column('visual_focus', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['layout_chapters.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_layout_pages_chapter_id'), 'layout_pages', ['chapter_id'], unique=False)

    op.create_table('layout_shots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('page_id', sa.UUID(), nullable=False),
        sa.Column('shot_id', sa.String(length=10), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['page_id'], ['layout_pages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_layout_shots_page_id'), 'layout_shots', ['page_id'], unique=False)

    op.create_table('image_prompts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('page_id', sa.UUID(), nullable=False),
        sa.Column('full_prompt', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('model_params', sa.JSON(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['page_id'], ['layout_pages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_image_prompts_page_id'), 'image_prompts', ['page_id'], unique=False)

    op.create_table('reference_matches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('page_id', sa.UUID(), nullable=False),
        sa.Column('ref_ids', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['page_id'], ['layout_pages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reference_matches_page_id'), 'reference_matches', ['page_id'], unique=False)

    op.create_table('generated_images',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('page_id', sa.UUID(), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_url', sa.String(length=500), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('model_params', sa.JSON(), nullable=True),
        sa.Column('is_selected', sa.String(length=20), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['page_id'], ['layout_pages.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generated_images_page_id'), 'generated_images', ['page_id'], unique=False)

    # ====== 9. tasks ======
    op.create_table('tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('logs', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'], unique=False)
    op.create_index(op.f('ix_tasks_task_type'), 'tasks', ['task_type'], unique=False)
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)
    op.create_index(
        'uq_tasks_active_dedup',
        'tasks',
        ['project_id', 'task_type'],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    # ====== 10. world_buildings / style_templates / scene_assets / props / buildings / outfits ======
    op.create_table('world_buildings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('era', sa.String(length=100), nullable=True),
        sa.Column('era_type', sa.String(length=50), nullable=True),
        sa.Column('time_span', sa.String(length=100), nullable=True),
        sa.Column('background', sa.Text(), nullable=True),
        sa.Column('core_tags', sa.JSON(), nullable=True),
        sa.Column('region_style', sa.String(length=100), nullable=True),
        sa.Column('civilization_level', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('cover_image', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_world_buildings_project_id'), 'world_buildings', ['project_id'], unique=False)

    op.create_table('style_templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('aspect_ratio', sa.String(length=20), nullable=True),
        sa.Column('width', sa.String(length=20), nullable=True),
        sa.Column('art_style', sa.Text(), nullable=True),
        sa.Column('coloring_style', sa.Text(), nullable=True),
        sa.Column('lineart_style', sa.Text(), nullable=True),
        sa.Column('lighting_style', sa.Text(), nullable=True),
        sa.Column('negative_prompt', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_style_templates_project_id'), 'style_templates', ['project_id'], unique=False)

    op.create_table('scene_assets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('world_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('aliases', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('season', sa.String(length=50), nullable=True),
        sa.Column('weather', sa.String(length=50), nullable=True),
        sa.Column('time_of_day', sa.String(length=50), nullable=True),
        sa.Column('lighting', sa.String(length=100), nullable=True),
        sa.Column('atmosphere', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['world_buildings.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scene_assets_world_id'), 'scene_assets', ['world_id'], unique=False)

    op.create_table('props',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('world_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('visual_description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['world_buildings.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_props_world_id'), 'props', ['world_id'], unique=False)

    op.create_table('buildings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('world_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('style', sa.String(length=100), nullable=True),
        sa.Column('interior_exterior', sa.String(length=20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('interior_description', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['world_buildings.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_buildings_world_id'), 'buildings', ['world_id'], unique=False)

    op.create_table('outfits',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('world_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('style', sa.String(length=100), nullable=True),
        sa.Column('belongs_to_character', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('color_scheme', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['world_id'], ['world_buildings.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outfits_world_id'), 'outfits', ['world_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_outfits_world_id'), table_name='outfits')
    op.drop_table('outfits')
    op.drop_index(op.f('ix_buildings_world_id'), table_name='buildings')
    op.drop_table('buildings')
    op.drop_index(op.f('ix_props_world_id'), table_name='props')
    op.drop_table('props')
    op.drop_index(op.f('ix_scene_assets_world_id'), table_name='scene_assets')
    op.drop_table('scene_assets')
    op.drop_index(op.f('ix_style_templates_project_id'), table_name='style_templates')
    op.drop_table('style_templates')
    op.drop_index(op.f('ix_world_buildings_project_id'), table_name='world_buildings')
    op.drop_table('world_buildings')
    op.drop_index('uq_tasks_active_dedup', table_name='tasks')
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_task_type'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_generated_images_page_id'), table_name='generated_images')
    op.drop_table('generated_images')
    op.drop_index(op.f('ix_reference_matches_page_id'), table_name='reference_matches')
    op.drop_table('reference_matches')
    op.drop_index(op.f('ix_image_prompts_page_id'), table_name='image_prompts')
    op.drop_table('image_prompts')
    op.drop_index(op.f('ix_layout_shots_page_id'), table_name='layout_shots')
    op.drop_table('layout_shots')
    op.drop_index(op.f('ix_layout_pages_chapter_id'), table_name='layout_pages')
    op.drop_table('layout_pages')
    op.drop_index(op.f('ix_layout_chapters_novel_id'), table_name='layout_chapters')
    op.drop_table('layout_chapters')
    op.drop_index(op.f('ix_storyboard_shots_chapter_id'), table_name='storyboard_shots')
    op.drop_table('storyboard_shots')
    op.drop_index(op.f('ix_storyboard_chapters_novel_id'), table_name='storyboard_chapters')
    op.drop_table('storyboard_chapters')
    op.drop_index(op.f('ix_script_shots_chapter_id'), table_name='script_shots')
    op.drop_table('script_shots')
    op.drop_index(op.f('ix_script_chapters_novel_id'), table_name='script_chapters')
    op.drop_table('script_chapters')
    op.drop_index(op.f('ix_editor_versions_chapter_id'), table_name='editor_versions')
    op.drop_table('editor_versions')
    op.drop_index(op.f('ix_paragraphs_chapter_id'), table_name='paragraphs')
    op.drop_table('paragraphs')
    op.drop_index(op.f('ix_chapters_status'), table_name='chapters')
    op.drop_index(op.f('ix_chapters_novel_id'), table_name='chapters')
    op.drop_table('chapters')
    op.drop_index(op.f('ix_character_relations_project_id'), table_name='character_relations')
    op.drop_index(op.f('ix_character_relations_character_b_id'), table_name='character_relations')
    op.drop_index(op.f('ix_character_relations_character_a_id'), table_name='character_relations')
    op.drop_table('character_relations')
    op.drop_index(op.f('ix_character_reference_images_state_id'), table_name='character_reference_images')
    op.drop_index(op.f('ix_character_reference_images_character_id'), table_name='character_reference_images')
    op.drop_table('character_reference_images')
    op.drop_index(op.f('ix_character_outfits_character_id'), table_name='character_outfits')
    op.drop_table('character_outfits')
    op.drop_index(op.f('ix_character_states_character_id'), table_name='character_states')
    op.drop_table('character_states')
    op.drop_index(op.f('ix_characters_role_type'), table_name='characters')
    op.drop_index(op.f('ix_characters_name'), table_name='characters')
    op.drop_index(op.f('ix_characters_stable_key'), table_name='characters')
    op.drop_index(op.f('ix_characters_project_id'), table_name='characters')
    op.drop_table('characters')
    op.drop_index(op.f('ix_novels_project_id'), table_name='novels')
    op.drop_table('novels')
    op.drop_index(op.f('ix_prompt_modules_template_id'), table_name='prompt_modules')
    op.drop_table('prompt_modules')
    op.drop_index(op.f('ix_prompt_templates_is_active'), table_name='prompt_templates')
    op.drop_table('prompt_templates')
    op.drop_table('system_logs')
    op.drop_table('notifications')
    op.drop_table('plugins')
    op.drop_index(op.f('ix_projects_user_id'), table_name='projects')
    op.drop_table('projects')
    op.drop_table('image_gen_config')
    op.drop_table('llm_config')
    op.drop_table('users')
