"""测试 TaskProgressTracker 状态机（mock DB，不依赖真实数据库）。"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infra.task_progress import TaskProgressTracker
from app.models.task import Task


def _make_task(status="queued", progress=0):
    return Task(
        id=uuid.uuid4(),
        project_id=None,
        task_type="test_task",
        status=status,
        progress=progress,
        logs=[],
    )


@pytest.fixture
def tracker():
    return TaskProgressTracker(_make_task())


@pytest.fixture
def mock_db(monkeypatch):
    """替换 async_session_factory 与 WebSocket 广播。"""
    fake_session = AsyncMock()
    fake_result = MagicMock()
    fake_result.rowcount = 1
    fake_session.execute.return_value = fake_result

    fake_factory = MagicMock()
    fake_factory.return_value.__aenter__.return_value = fake_session

    monkeypatch.setattr("app.infra.task_progress.async_session_factory", fake_factory)
    broadcast = AsyncMock()
    monkeypatch.setattr("app.infra.task_progress.task_event_manager.broadcast", broadcast)
    return fake_session


async def test_set_running(tracker, mock_db):
    await tracker.set_running("开始执行")
    assert tracker.task.status == "running"
    assert tracker.task.started_at is not None
    assert tracker.task.progress == 0
    assert tracker.task.logs[-1]["message"] == "开始执行"


async def test_update_progress_clamps_range(tracker, mock_db):
    await tracker.update_progress(150)
    assert tracker.task.progress == 100
    await tracker.update_progress(-10)
    assert tracker.task.progress == 0


async def test_update_progress_with_message(tracker, mock_db):
    await tracker.update_progress(50, "处理中")
    assert tracker.task.progress == 50
    assert tracker.task.logs[-1]["message"] == "处理中"


async def test_complete(tracker, mock_db):
    await tracker.complete({"result": 1}, "完成")
    assert tracker.task.status == "completed"
    assert tracker.task.progress == 100
    assert tracker.task.output_data == {"result": 1}
    assert tracker.task.completed_at is not None


async def test_fail(tracker, mock_db):
    await tracker.fail("出错了")
    assert tracker.task.status == "failed"
    assert tracker.task.error_message == "出错了"
    assert tracker.task.logs[-1]["level"] == "error"


async def test_flush_skipped_on_status_mismatch(tracker, monkeypatch):
    """_flush 命中状态不匹配（rowcount=0）时返回 False，不广播。"""
    fake_session = AsyncMock()
    fake_result = MagicMock()
    fake_result.rowcount = 0
    fake_session.execute.return_value = fake_result
    fake_factory = MagicMock()
    fake_factory.return_value.__aenter__.return_value = fake_session
    monkeypatch.setattr("app.infra.task_progress.async_session_factory", fake_factory)
    broadcast = AsyncMock()
    monkeypatch.setattr("app.infra.task_progress.task_event_manager.broadcast", broadcast)

    # task 当前 running，complete 期望 queued/running → 应成功（running 在集合内）
    # 直接构造一个已 failed 的 task 来验证不匹配分支
    tracker2 = TaskProgressTracker(_make_task(status="failed"))
    await tracker2.complete({"x": 1})
    assert not broadcast.called


async def test_flush_db_error_does_not_raise(tracker, monkeypatch):
    """DB 异常时 _flush 返回 False，complete 不抛异常、不广播。"""
    fake_session = AsyncMock()
    fake_session.execute.side_effect = RuntimeError("db down")
    fake_factory = MagicMock()
    fake_factory.return_value.__aenter__.return_value = fake_session
    monkeypatch.setattr("app.infra.task_progress.async_session_factory", fake_factory)
    broadcast = AsyncMock()
    monkeypatch.setattr("app.infra.task_progress.task_event_manager.broadcast", broadcast)

    await tracker.complete({"x": 1})  # 不应抛异常
    assert not broadcast.called
