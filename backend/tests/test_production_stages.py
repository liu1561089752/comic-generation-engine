"""测试生产进度 8 工序计算 _get_production_stages（mock DB）。"""
import uuid

import pytest

from app.routers.dashboard import _get_production_stages
from tests.conftest import FakeDB

PROJECT_ID = uuid.uuid4()


async def test_empty_project_all_pending():
    db = FakeDB({})
    stages = await _get_production_stages(db, PROJECT_ID)

    assert len(stages) == 8
    for s in stages:
        assert s["status"] == "pending"
        assert s["progress"] == 0
    # 画面生成为 0
    img = next(s for s in stages if s["stage"] == "image_generation")
    assert img["progress"] == 0


async def test_full_completion():
    db = FakeDB({
        "novels": 1,
        "characters": 2,
        "character_reference_images": 2,
        "world_buildings": 1,
        "_assets_union": {"total": 7, "with_img": 7},  # 场景3+道具2+建筑1+服装1
        "script_chapters": 1,
        "storyboard_chapters": 1,
        "layout_chapters": 1,
        "layout_pages": 10,
        "generated_images": 10,
        "tasks": 1,
    })
    stages = await _get_production_stages(db, PROJECT_ID)

    for s in stages:
        assert s["status"] == "completed", f"{s['stage']} 应为 completed"
    img = next(s for s in stages if s["stage"] == "image_generation")
    assert img["progress"] == 100


async def test_partial_progress():
    """画面生成有中间进度；角色图不全则角色设计未完成。"""
    db = FakeDB({
        "novels": 1,
        "characters": 2,                    # 2 个角色
        "character_reference_images": 1,    # 只有 1 个有图 → 未完成
        "world_buildings": 1,
        "_assets_union": {"total": 2, "with_img": 0},  # 资产无图 → 世界观未完成
        "script_chapters": 1,
        "storyboard_chapters": 1,
        "layout_chapters": 1,
        "layout_pages": 10,
        "generated_images": 5,              # 5/10 = 50%
        "tasks": 0,
    })
    stages = await _get_production_stages(db, PROJECT_ID)
    by_stage = {s["stage"]: s for s in stages}

    # 小说/脚本/分镜/排版：有数据 → 完成
    assert by_stage["novel_import"]["status"] == "completed"
    assert by_stage["script_generation"]["status"] == "completed"
    assert by_stage["storyboard"]["status"] == "completed"
    assert by_stage["layout"]["status"] == "completed"

    # 角色：2 个角色仅 1 个有图 → 未完成
    assert by_stage["character_design"]["status"] == "pending"

    # 世界观：资产无图 → 未完成
    assert by_stage["world_building"]["status"] == "pending"

    # 画面生成：5/10 → in_progress 且进度 50
    img = by_stage["image_generation"]
    assert img["status"] == "in_progress"
    assert img["progress"] == 50

    # 导出：无 export 任务 → 未完成
    assert by_stage["export"]["status"] == "pending"


async def test_image_progress_rounding():
    """1/3 页 → 33%；2/3 → 67%。"""
    db = FakeDB({
        "novels": 1,
        "characters": 0,
        "world_buildings": 0,
        "script_chapters": 1,
        "storyboard_chapters": 1,
        "layout_chapters": 1,
        "layout_pages": 3,
        "generated_images": 1,
    })
    stages = await _get_production_stages(db, PROJECT_ID)
    img = next(s for s in stages if s["stage"] == "image_generation")
    assert img["progress"] == 33
