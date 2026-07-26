"""异步文件操作工具 — 避免在 async 函数中阻塞事件循环。

所有文件 I/O 通过 asyncio.to_thread 委托给线程池，
适用于图片读写、目录操作等可能耗时的场景。
"""
import asyncio
import os
import shutil
from typing import Optional


async def write_bytes(path: str, data: bytes) -> None:
    """异步写入字节数据到文件。"""
    await asyncio.to_thread(_write_bytes_sync, path, data)


def _write_bytes_sync(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


async def read_bytes(path: str) -> Optional[bytes]:
    """异步读取文件字节，文件不存在返回 None。"""
    return await asyncio.to_thread(_read_bytes_sync, path)


def _read_bytes_sync(path: str) -> Optional[bytes]:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


async def makedirs(path: str, exist_ok: bool = True) -> None:
    """异步创建目录。

    即使在 exist_ok=True 时，Windows 上并发任务同时创建同一目录
    也可能因 TOCTOU 竞争触发 WinError 183。重试一次兜底。
    """
    try:
        # exist_ok 必须用关键字传参：os.makedirs 的第二个位置参数是 mode
        await asyncio.to_thread(os.makedirs, path, exist_ok=exist_ok)
    except FileExistsError:
        if not exist_ok:
            raise


async def rmtree(path: str, ignore_errors: bool = False) -> None:
    """异步递归删除目录。"""
    await asyncio.to_thread(shutil.rmtree, path, ignore_errors)


async def file_exists(path: str) -> bool:
    """异步检查文件是否存在。"""
    return await asyncio.to_thread(os.path.exists, path)


async def remove_file(path: str) -> None:
    """异步删除文件（忽略不存在）。"""
    await asyncio.to_thread(_remove_file_sync, path)


def _remove_file_sync(path: str) -> None:
    if os.path.isfile(path):
        os.remove(path)


async def move_file(src: str, dst: str) -> None:
    """异步移动文件。"""
    await asyncio.to_thread(shutil.move, src, dst)


async def write_bytes_atomic(path: str, data: bytes) -> None:
    """原子写入字节数据：先写临时文件，再 rename 到目标路径。

    避免并发写入同一文件时产生损坏。
    """
    await asyncio.to_thread(_write_bytes_atomic_sync, path, data)


def _write_bytes_atomic_sync(path: str, data: bytes) -> None:
    import tempfile
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
