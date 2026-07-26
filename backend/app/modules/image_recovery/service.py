"""Image Recovery Service - 从 GRS AI 积分记录中恢复未生成的漫画页图片.

通过查询 GRS AI 的积分记录 API，找到已成功生成但未保存到数据库的图片，
下载并写入 GeneratedImage。
"""
import asyncio
import json
import logging
import os
import re
import time
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import async_session_factory
from app.infra.file_utils import makedirs, write_bytes_atomic
from app.models.layout import LayoutChapter, LayoutPage, GeneratedImage

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

# GRS AI 积分记录查询地址
CREDITS_LOG_URL = "https://grsaiapi.com/client/grsai/getCreditsLogList"


async def _query_credits_log(
    authorization: str,
    xtx: str,
    page: int,
    limit: int,
    last_create_time: int,
) -> dict:
    """查询 GRS AI 积分记录（单页）."""
    headers = {
        "Authorization": authorization,
        "xtx": xtx,
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
        "Referer": "https://grsai.com/",
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-mobile": "?0",
    }
    payload = {
        "page": page,
        "limit": limit,
        "locale": "zh",
        "lastCreateTime": last_create_time,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(CREDITS_LOG_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()


def _extract_shot_id_from_prompt(prompt: str) -> Optional[str]:
    """从 prompt 中提取 shotId.

    支持格式:
      【shotId】：01  或  【shotId】: S1      （shotId 在括号后）
      【shotId：01】  或  【shotId: S1】     （shotId 在括号内）
    """
    # 格式1: 【shotId】: value
    match = re.search(r'【shotId】[：:]\s*(\S+)', prompt)
    if match:
        return match.group(1).strip()

    # 格式2: 【shotId：value】 或 【shotId: value】
    match = re.search(r'【shotId[：:]\s*(\S+?)】', prompt)
    if match:
        return match.group(1).strip()

    return None


def _parse_result_for_image_url(result_str: str) -> Optional[str]:
    """从 taskData.result JSON 字符串中解析图片 URL."""
    try:
        result_data = json.loads(result_str)
        if result_data.get("status") == "succeeded":
            results = result_data.get("results", [])
            if results and "url" in results[0]:
                return results[0]["url"]
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return None


class ImageRecoveryService:
    """图片恢复服务 - 从 GRS AI 积分记录中恢复漫画页图片."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_pages_without_images(self, novel_id: UUID) -> list:
        """获取 novel 下所有没有图片的排版页（按全局顺序排列）.

        必须 selectinload(shots)：AsyncSession 下延迟加载 page.shots 会抛 MissingGreenlet。
        """
        result = await self.session.execute(
            select(LayoutPage)
            .options(selectinload(LayoutPage.shots))
            .join(LayoutChapter, LayoutPage.chapter_id == LayoutChapter.id)
            .outerjoin(GeneratedImage, GeneratedImage.page_id == LayoutPage.id)
            .where(LayoutChapter.novel_id == novel_id)
            .where(GeneratedImage.id.is_(None))  # 没有已生成的图片
            .order_by(LayoutChapter.sort_order, LayoutPage.sort_order)
        )
        return list(result.scalars().all())

    async def recover_images(
        self,
        project_id: UUID,
        novel_id: UUID,
        authorization: str,
        xtx: str,
        limit: int,
        tracker=None,
    ) -> dict:
        """从 GRS AI 积分记录中恢复漫画页图片.

        流程:
        1. 获取所有没有图片的漫画页
        2. 提取每页的第一个 shotId
        3. 逐页查询 GRS AI 积分记录
        4. 匹配 shotId，下载图片，写入数据库
        """
        # Step 1: 获取所有需要补图的页面
        pages_needed = await self._get_pages_without_images(novel_id)
        if not pages_needed:
            return {"status": "ok", "message": "所有页面已有图片，无需补图", "recovered": 0, "total": 0}

        # Step 2: 建立 shotId -> 待补图页面队列的映射（只取每页第一个 shot）
        # p.shots 是 LayoutShot ORM 对象列表（不是 dict），按 sort_order 取首个镜头。
        # shot_id 只在章节内唯一，而积分记录的 prompt 里只有 shotId、没有章节/页面标识，
        # 无法反推章节；因此同一 shotId 下按全局顺序保留多个候选页面，
        # 匹配到记录时依次取用，避免同名 shotId 互相覆盖导致漏补。
        shot_to_pages = {}  # shotId -> [LayoutPage, ...]
        for p in pages_needed:
            shots = list(p.shots or [])
            if not shots:
                continue
            first_shot = min(shots, key=lambda s: (s.sort_order or 0))
            shot_id = (first_shot.shot_id or "").strip()
            if shot_id:
                shot_to_pages.setdefault(shot_id, []).append(p)

        if not shot_to_pages:
            return {
                "status": "ok",
                "message": "所有需补图的页面均无 shotId，无法匹配",
                "recovered": 0,
                "total": len(pages_needed),
            }

        logger.info(
            f"需要补图: {len(pages_needed)} 页, "
            f"待匹配 shotId 数: {len(shot_to_pages)}: {list(shot_to_pages.keys())}"
        )

        if tracker:
            await tracker.update_progress(0, f"需要补图 {len(pages_needed)} 页，开始查询积分记录...")

        # Step 3: 逐页查询积分记录
        # 计算需要的页数（limit 是用户指定的每页记录数）
        records_per_page = min(limit, 50)  # GRS API limit 上限
        max_api_pages = max(1, limit // records_per_page)  # 最多查这么多 API 页
        if max_api_pages > 10:
            max_api_pages = 10  # 最多查 10 页防止请求过多

        last_create_time = int(time.time())
        found_count = 0
        total_queried = 0
        recovered_pages = []
        download_tasks = []
        scanned_shot_ids = set()

        for api_page in range(1, max_api_pages + 1):
            if not any(shot_to_pages.values()):
                break  # 所有 shotId 都已匹配完

            try:
                response = await _query_credits_log(
                    authorization, xtx, api_page, records_per_page, last_create_time
                )
            except Exception as e:
                logger.error(f"查询积分记录失败 (page {api_page}): {e}")
                if tracker:
                    await tracker.update_progress(
                        int(api_page / max_api_pages * 50),
                        f"查询积分记录失败 (第 {api_page} 页): {e}",
                    )
                continue

            if response.get("code") != 0:
                logger.warning(f"积分记录 API 返回异常: {response.get('msg')}")
                continue

            data = response.get("data", {})
            records = data.get("list", [])
            if not records:
                break  # 没有更多记录了

            # 解析每一条记录，匹配 shotId
            for record in records:
                task_data = record.get("taskData", {}) or {}
                prompt = task_data.get("prompt", "")
                result_str = task_data.get("result", "")

                shot_id = _extract_shot_id_from_prompt(prompt)
                if not shot_id:
                    continue

                total_queried += 1
                scanned_shot_ids.add(shot_id)

                # 检查是否匹配需要补图的页
                candidates = shot_to_pages.get(shot_id)
                if candidates:
                    image_url = _parse_result_for_image_url(result_str)
                    if image_url:
                        page = candidates.pop(0)
                        download_tasks.append(
                            self._download_and_save(
                                project_id, novel_id, page, image_url
                            )
                        )
                        found_count += 1
                        recovered_pages.append(page.page_label)
                        logger.info(
                            f"匹配成功: 页面 {page.page_label} "
                            f"(shotId={shot_id}) -> {image_url[:80]}..."
                        )

            if tracker:
                progress = int(50 + (api_page / max_api_pages) * 40)
                await tracker.update_progress(
                    progress,
                    f"已查询 {api_page}/{max_api_pages} 页记录, "
                    f"找到 {found_count}/{len(pages_needed)} 页匹配",
                )

            # 如果本次查询的记录数少于请求数，说明已到最后一页
            if len(records) < records_per_page:
                break

        unmatched_shot_ids = [sid for sid, pages in shot_to_pages.items() if pages]

        logger.info(
            f"补图查询完成: 扫描 {total_queried} 条记录, "
            f"匹配 {found_count} 页, "
            f"未匹配: {unmatched_shot_ids}"
        )

        if tracker:
            await tracker.update_progress(90, f"开始下载 {len(download_tasks)} 张图片...")

        # Step 4: 并行下载图片并写入数据库
        if download_tasks:
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            fail_count = sum(1 for r in results if isinstance(r, Exception))

            logger.info(f"图片下载完成: 成功 {success_count}, 失败 {fail_count}")

            if tracker:
                await tracker.update_progress(100, f"补图完成: 成功 {success_count} 页, 失败 {fail_count} 页")

            return {
                "status": "ok",
                "recovered": success_count,
                "failed": fail_count,
                "total": len(pages_needed),
                "recovered_pages": recovered_pages,
                "unmatched": unmatched_shot_ids,
            }

        if tracker:
            await tracker.update_progress(100, "未找到可匹配的图片记录")

        return {
            "status": "ok",
            "recovered": 0,
            "total": len(pages_needed),
            "unmatched": unmatched_shot_ids,
            "scanned_shot_ids": list(scanned_shot_ids),
        }

    async def _download_and_save(
        self,
        project_id: UUID,
        novel_id: UUID,
        page: LayoutPage,
        image_url: str,
    ) -> bool:
        """下载图片并保存到数据库."""
        try:
            # Step 1: 下载图片
            storage_dir = os.path.join(
                settings.STORAGE_LOCAL_PATH,
                str(project_id),
                "generation",
                str(novel_id),
            )
            await makedirs(storage_dir, exist_ok=True)

            filename = f"{page.page_label}.png"
            filepath = os.path.join(storage_dir, filename)

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(
                    image_url,
                    headers={
                        "User-Agent": _USER_AGENT,
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    },
                )
                resp.raise_for_status()
                await write_bytes_atomic(filepath, resp.content)

            local_path = f"/storage/{project_id}/generation/{novel_id}/{filename}"

            # Step 2: 写入 GeneratedImage 记录
            async with async_session_factory() as write_session:
                # 同一 page_id 只保留一条记录：多条 selected 会让导出重复拼接同一页
                await write_session.execute(
                    sa_delete(GeneratedImage).where(GeneratedImage.page_id == page.id)
                )
                write_session.add(GeneratedImage(
                    page_id=page.id,
                    image_url=local_path,
                    is_selected="selected",
                ))
                await write_session.commit()

            logger.info(f"补图成功: 页面 {page.page_label} -> {local_path}")
            return True

        except Exception as e:
            logger.error(f"补图失败 页面 {page.page_label}: {e}")
            return False
