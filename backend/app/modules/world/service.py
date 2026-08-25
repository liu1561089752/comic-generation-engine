"""World service - 世界观管理服务 (migrated from app/services/world_service.py).

新架构规范：
- 不 import 任何 app.services.* / app.adapters.* / app.config / app.database 旧路径。
- AI 调用与生图调用一律采用短事务模式：AI 期间不持有 DB session，
  持久化时通过 async_session_factory() 开启独立短会话写入。
- 简单 CRUD 继续复用路由传入的 self.session。
"""
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.llm_utils import parse_llm_json
from app.infra.adapters.base_llm import ChatMessage
from app.infra.adapters.image_gen_adapter import ImageGenAdapter
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.file_utils import file_exists, makedirs, move_file, write_bytes_atomic
from app.models.world import (
    Building,
    Outfit,
    Prop,
    SceneAsset,
    WorldBuilding,
)
from app.schemas.world_schema import (
    BuildingCreate,
    OutfitCreate,
    PropCreate,
    SceneAssetCreate,
)
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


# 下载远程图片时使用的浏览器风格请求头，绕过 Cloudflare 等安全检测
_IMAGE_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://grsai.dakka.com.cn/",
}


class WorldService:
    """世界观管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.world_repo = BaseRepository(WorldBuilding, session)
        self.scene_asset_repo = BaseRepository(SceneAsset, session)
        self.prop_repo = BaseRepository(Prop, session)
        self.building_repo = BaseRepository(Building, session)
        self.outfit_repo = BaseRepository(Outfit, session)

    # ==================================================================
    # 世界观 CRUD
    # ==================================================================

    async def get_world(self, world_id: UUID) -> Optional[WorldBuilding]:
        return await self.world_repo.get(world_id)

    async def list_worlds(
        self, project_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[WorldBuilding], int]:
        return await self.world_repo.list(project_id=project_id, skip=skip, limit=limit)

    async def update_world(self, world_id: UUID, data: dict) -> Optional[WorldBuilding]:
        return await self.world_repo.update(world_id, **data)

    async def delete_world(self, world_id: UUID) -> bool:
        return await self.world_repo.delete(world_id)

    async def ai_create_world(self, project_id: UUID, novel_text: str) -> WorldBuilding:
        """调用 LLM 提取世界观设定并自动创建。

        约束：一个项目只允许一个世界观；已存在世界观时拒绝再次创建。

        短事务模式：AI 调用期间不持有 DB session，避免连接池耗尽。
        """
        # 校验：一个项目只允许一个世界观
        existing = await self.world_repo.list_all(project_id=project_id)
        if existing:
            raise ValueError("该项目已存在世界观，每个项目仅允许创建一个世界观")

        # Step 1: AI call (no DB session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("world_extraction")
        messages = [
            ChatMessage("system", system_prompt),
            ChatMessage("user", novel_text),
        ]
        result = await llm.chat(messages, temperature=0.5)

        try:
            data = parse_llm_json(result.content)
        except ValueError as e:
            raise ValueError(f"解析AI返回结果失败: {str(e)}")

        # Step 2: Short write — create world in independent session
        async with async_session_factory() as write_session:
            world_repo = BaseRepository(WorldBuilding, write_session)
            world = await world_repo.create(
                project_id=project_id,
                name=data.get("name", "未命名世界观"),
                era_type=data.get("era_type"),
                time_span=data.get("time_span"),
                background=data.get("background"),
                core_tags=data.get("core_tags"),
                region_style=data.get("region_style"),
                civilization_level=data.get("civilization_level"),
                description=data.get("description"),
            )
            await write_session.commit()
            logger.info(f"AI 已自动创建世界观: {world.name}")
            return world

    # ==================================================================
    # 场景资产 CRUD
    # ==================================================================

    async def create_scene_asset(self, world_id: UUID, data: SceneAssetCreate) -> SceneAsset:
        return await self.scene_asset_repo.create(world_id=world_id, **data.model_dump())

    async def list_scene_assets(
        self, world_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[SceneAsset], int]:
        return await self.scene_asset_repo.list(world_id=world_id, skip=skip, limit=limit)

    async def get_scene_asset(self, asset_id: UUID) -> Optional[SceneAsset]:
        return await self.scene_asset_repo.get(asset_id)

    async def update_scene_asset(self, asset_id: UUID, data: dict) -> Optional[SceneAsset]:
        return await self.scene_asset_repo.update(asset_id, **data)

    async def delete_scene_asset(self, asset_id: UUID) -> bool:
        return await self.scene_asset_repo.delete(asset_id)

    async def ai_extract_scene_assets(self, world_id: UUID, novel_text: str) -> List[SceneAsset]:
        """短事务模式：AI 调用期间不持有 DB session。

        按名称 upsert：同名资产保留原 id（及已生成的 image_url），只更新描述类字段；
        本次未出现的旧资产才删除。id 必须稳定，否则 ReferenceMatch.ref_ids 里存的
        旧 id 会全部变成死链，且无法通过重新匹配自动修复。
        """
        # Step 1: AI call (no DB session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("scene_extraction")
        messages = [
            ChatMessage("system", system_prompt),
            ChatMessage("user", novel_text),
        ]
        result = await llm.chat(messages, temperature=0.5)

        try:
            data = parse_llm_json(result.content)
        except ValueError as e:
            logger.error(f"场景提取 parse_llm_json 失败, 原始内容={result.content[:500]}")
            raise ValueError(f"解析AI返回结果失败: {str(e)}")

        scenes = data.get("scenes", [])
        if not scenes:
            logger.warning(f"场景提取: AI 返回中无 scenes 键, 可用键={list(data.keys())}, 内容前200字={result.content[:200]}")
            return []

        # Step 2: Short write — read old + upsert by name in independent session
        async with async_session_factory() as write_session:
            scene_asset_repo = BaseRepository(SceneAsset, write_session)

            old_assets = await scene_asset_repo.list_all(world_id=world_id)
            old_by_name = {a.name: a for a in old_assets}
            kept_ids = set()

            created_assets: List[SceneAsset] = []
            for scene in scenes:
                name = scene.get("name", "")
                fields = {
                    "description": scene.get("description", ""),
                    "season": scene.get("season"),
                    "weather": scene.get("weather"),
                    "time_of_day": scene.get("time_of_day"),
                    "lighting": scene.get("lighting"),
                    "atmosphere": scene.get("atmosphere"),
                }
                existing = old_by_name.get(name)
                if existing is not None:
                    asset = await scene_asset_repo.update(existing.id, **fields)
                else:
                    asset = await scene_asset_repo.create(
                        world_id=world_id, name=name, **fields
                    )
                kept_ids.add(asset.id)
                created_assets.append(asset)

            # 本次提取结果中未出现的旧资产才删除
            for old in old_assets:
                if old.id not in kept_ids:
                    await write_session.delete(old)

            await write_session.commit()
            logger.info(f"AI 已提取 {len(created_assets)} 个场景资产")
            return created_assets

    async def generate_scene_image(self, asset_id: UUID, project_id: UUID) -> dict:
        """生成场景资产图片（短事务模式）。"""
        return await self._generate_entity_image(
            SceneAsset,
            asset_id,
            project_id,
            subdir="scene_assets",
            id_key="asset_id",
            name_key="asset_name",
            not_found_msg="场景资产不存在",
            empty_msg="场景描述为空",
        )

    # ==================================================================
    # 道具 CRUD
    # ==================================================================

    async def create_prop(self, world_id: UUID, data: PropCreate) -> Prop:
        return await self.prop_repo.create(world_id=world_id, **data.model_dump())

    async def list_props(
        self, world_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Prop], int]:
        return await self.prop_repo.list(world_id=world_id, skip=skip, limit=limit)

    async def get_prop(self, prop_id: UUID) -> Optional[Prop]:
        return await self.prop_repo.get(prop_id)

    async def update_prop(self, prop_id: UUID, data: dict) -> Optional[Prop]:
        return await self.prop_repo.update(prop_id, **data)

    async def delete_prop(self, prop_id: UUID) -> bool:
        return await self.prop_repo.delete(prop_id)

    async def ai_extract_props(self, world_id: UUID, novel_text: str) -> List[Prop]:
        """短事务模式：AI 调用期间不持有 DB session。

        按名称 upsert：同名道具保留原 id（及已生成的 image_url），只更新描述类字段；
        本次未出现的旧道具才删除。id 必须稳定，否则 ReferenceMatch.ref_ids 里存的
        旧 id 会全部变成死链，且无法通过重新匹配自动修复。
        """
        # Step 1: AI call (no DB session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("prop_extraction")
        messages = [
            ChatMessage("system", system_prompt),
            ChatMessage("user", novel_text),
        ]
        result = await llm.chat(messages, temperature=0.5)

        try:
            data = parse_llm_json(result.content)
        except ValueError as e:
            raise ValueError(f"解析AI返回结果失败: {str(e)}")

        props = data.get("props", [])
        if not props:
            return []

        # Step 2: Short write — read old + upsert by name in independent session
        async with async_session_factory() as write_session:
            prop_repo = BaseRepository(Prop, write_session)

            old_props = await prop_repo.list_all(world_id=world_id)
            old_by_name = {a.name: a for a in old_props}
            kept_ids = set()

            created_props: List[Prop] = []
            for prop in props:
                name = prop.get("name", "")
                fields = {
                    "category": prop.get("category"),
                    "description": prop.get("description", ""),
                    "visual_description": prop.get("visual_description"),
                }
                existing = old_by_name.get(name)
                if existing is not None:
                    item = await prop_repo.update(existing.id, **fields)
                else:
                    item = await prop_repo.create(
                        world_id=world_id, name=name, **fields
                    )
                kept_ids.add(item.id)
                created_props.append(item)

            # 本次提取结果中未出现的旧道具才删除
            for old in old_props:
                if old.id not in kept_ids:
                    await write_session.delete(old)

            await write_session.commit()
            logger.info(f"AI 已提取 {len(created_props)} 个道具")
            return created_props

    async def generate_prop_image(self, prop_id: UUID, project_id: UUID) -> dict:
        """生成道具图片（短事务模式）。"""
        return await self._generate_entity_image(
            Prop,
            prop_id,
            project_id,
            subdir="props",
            id_key="prop_id",
            name_key="prop_name",
            not_found_msg="道具不存在",
            empty_msg="道具描述为空",
        )

    # ==================================================================
    # 建筑 CRUD
    # ==================================================================

    async def create_building(self, world_id: UUID, data: BuildingCreate) -> Building:
        return await self.building_repo.create(world_id=world_id, **data.model_dump())

    async def list_buildings(
        self, world_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Building], int]:
        return await self.building_repo.list(world_id=world_id, skip=skip, limit=limit)

    async def get_building(self, building_id: UUID) -> Optional[Building]:
        return await self.building_repo.get(building_id)

    async def update_building(self, building_id: UUID, data: dict) -> Optional[Building]:
        return await self.building_repo.update(building_id, **data)

    async def delete_building(self, building_id: UUID) -> bool:
        return await self.building_repo.delete(building_id)

    async def ai_extract_buildings(self, world_id: UUID, novel_text: str) -> List[Building]:
        """短事务模式：AI 调用期间不持有 DB session。

        按名称 upsert：同名建筑保留原 id（及已生成的 image_url），只更新描述类字段；
        本次未出现的旧建筑才删除。id 必须稳定，否则 ReferenceMatch.ref_ids 里存的
        旧 id 会全部变成死链，且无法通过重新匹配自动修复。
        """
        # Step 1: AI call (no DB session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("building_extraction")
        messages = [
            ChatMessage("system", system_prompt),
            ChatMessage("user", novel_text),
        ]
        result = await llm.chat(messages, temperature=0.5)

        try:
            data = parse_llm_json(result.content)
        except ValueError as e:
            raise ValueError(f"解析AI返回结果失败: {str(e)}")

        buildings = data.get("buildings", [])
        if not buildings:
            return []

        # Step 2: Short write — read old + upsert by name in independent session
        async with async_session_factory() as write_session:
            building_repo = BaseRepository(Building, write_session)

            old_buildings = await building_repo.list_all(world_id=world_id)
            old_by_name = {a.name: a for a in old_buildings}
            kept_ids = set()

            created_buildings: List[Building] = []
            for building in buildings:
                name = building.get("name", "")
                fields = {
                    "style": building.get("style"),
                    "interior_exterior": building.get("interior_exterior"),
                    "description": building.get("description", ""),
                    "interior_description": building.get("interior_description"),
                }
                existing = old_by_name.get(name)
                if existing is not None:
                    item = await building_repo.update(existing.id, **fields)
                else:
                    item = await building_repo.create(
                        world_id=world_id, name=name, **fields
                    )
                kept_ids.add(item.id)
                created_buildings.append(item)

            # 本次提取结果中未出现的旧建筑才删除
            for old in old_buildings:
                if old.id not in kept_ids:
                    await write_session.delete(old)

            await write_session.commit()
            logger.info(f"AI 已提取 {len(created_buildings)} 个建筑")
            return created_buildings

    async def generate_building_image(self, building_id: UUID, project_id: UUID) -> dict:
        """生成建筑图片（短事务模式）。"""
        return await self._generate_entity_image(
            Building,
            building_id,
            project_id,
            subdir="buildings",
            id_key="building_id",
            name_key="building_name",
            not_found_msg="建筑不存在",
            empty_msg="建筑描述为空",
        )

    # ==================================================================
    # 服装 CRUD
    # ==================================================================

    async def create_outfit(self, world_id: UUID, data: OutfitCreate) -> Outfit:
        return await self.outfit_repo.create(world_id=world_id, **data.model_dump())

    async def list_outfits(
        self, world_id: UUID, skip: int = 0, limit: int = 20
    ) -> Tuple[List[Outfit], int]:
        return await self.outfit_repo.list(world_id=world_id, skip=skip, limit=limit)

    async def get_outfit(self, outfit_id: UUID) -> Optional[Outfit]:
        return await self.outfit_repo.get(outfit_id)

    async def update_outfit(self, outfit_id: UUID, data: dict) -> Optional[Outfit]:
        return await self.outfit_repo.update(outfit_id, **data)

    async def delete_outfit(self, outfit_id: UUID) -> bool:
        return await self.outfit_repo.delete(outfit_id)

    async def ai_extract_outfits(self, world_id: UUID, novel_text: str) -> List[Outfit]:
        """短事务模式：AI 调用期间不持有 DB session。

        按名称 upsert：同名服装保留原 id（及已生成的 image_url），只更新描述类字段；
        本次未出现的旧服装才删除。id 必须稳定，否则 ReferenceMatch.ref_ids 里存的
        旧 id 会全部变成死链，且无法通过重新匹配自动修复。
        """
        # Step 1: AI call (no DB session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("outfit_extraction")
        messages = [
            ChatMessage("system", system_prompt),
            ChatMessage("user", novel_text),
        ]
        result = await llm.chat(messages, temperature=0.5)

        try:
            data = parse_llm_json(result.content)
        except ValueError as e:
            raise ValueError(f"解析AI返回结果失败: {str(e)}")

        outfits = data.get("outfits", [])
        if not outfits:
            return []

        # Step 2: Short write — read old + upsert by name in independent session
        async with async_session_factory() as write_session:
            outfit_repo = BaseRepository(Outfit, write_session)

            old_outfits = await outfit_repo.list_all(world_id=world_id)
            old_by_name = {a.name: a for a in old_outfits}
            kept_ids = set()

            created_outfits: List[Outfit] = []
            for outfit in outfits:
                name = outfit.get("name", "")
                fields = {
                    "style": outfit.get("style"),
                    "description": outfit.get("description", ""),
                    "belongs_to_character": outfit.get("belongs_to_character"),
                    "color_scheme": outfit.get("color_scheme"),
                }
                existing = old_by_name.get(name)
                if existing is not None:
                    item = await outfit_repo.update(existing.id, **fields)
                else:
                    item = await outfit_repo.create(
                        world_id=world_id, name=name, **fields
                    )
                kept_ids.add(item.id)
                created_outfits.append(item)

            # 本次提取结果中未出现的旧服装才删除
            for old in old_outfits:
                if old.id not in kept_ids:
                    await write_session.delete(old)

            await write_session.commit()
            logger.info(f"AI 已提取 {len(created_outfits)} 个服装")
            return created_outfits

    async def generate_outfit_image(self, outfit_id: UUID, project_id: UUID) -> dict:
        """生成服装图片（短事务模式）。"""
        return await self._generate_entity_image(
            Outfit,
            outfit_id,
            project_id,
            subdir="outfits",
            id_key="outfit_id",
            name_key="outfit_name",
            not_found_msg="服装不存在",
            empty_msg="服装描述为空",
        )

    # ==================================================================
    # 生图内部辅助（短事务模式）
    # ==================================================================

    async def _generate_entity_image(
        self,
        model_cls,
        entity_id: UUID,
        project_id: UUID,
        subdir: str,
        id_key: str,
        name_key: str,
        not_found_msg: str,
        empty_msg: str,
    ) -> dict:
        """生图通用流程（短事务模式）：

        1. 短读取出实体（捕获 description / name / 旧 image_url）
        2. AI 生图（不持有 session）
        3. 文件 I/O 下载到本地、旧图移入回收站（不持有 session）
        4. 短写入更新 image_url
        """
        # Step 1: Short read — get entity fields
        async with async_session_factory() as read_session:
            repo = BaseRepository(model_cls, read_session)
            entity = await repo.get(entity_id)
            if entity is None:
                raise ValueError(not_found_msg)
            description = entity.description
            name = entity.name
            old_image_url = entity.image_url

        if not description:
            raise ValueError(empty_msg)

        # Step 2: AI call (no session held)
        image_gen = ImageGenAdapter()
        gen_result = await image_gen.generate(description, params={"aspectRatio": "16:9"})
        image_url = gen_result.get("image_url", "")
        local_path = ""

        # Step 3: File I/O — recycle old image + download new (no session held)
        if image_url:
            local_path = await self._persist_image_locally(
                image_url, old_image_url, project_id, entity_id, subdir
            )

        # Step 4: Short write — update image_url
        final_url = local_path or image_url
        if final_url:
            async with async_session_factory() as write_session:
                repo = BaseRepository(model_cls, write_session)
                await repo.update(entity_id, image_url=final_url)
                await write_session.commit()

        return {
            id_key: str(entity_id),
            name_key: name,
            "image_url": final_url,
        }

    async def _persist_image_locally(
        self,
        image_url: str,
        old_image_url: Optional[str],
        project_id: UUID,
        entity_id: UUID,
        subdir: str,
    ) -> str:
        """下载远程图片到本地，并把旧图片移入回收站。

        返回本地相对路径（如 /storage/{project_id}/{subdir}/{entity_id}/{file}.png）；
        下载失败时返回空字符串，调用方将回退使用原始 URL。
        """
        storage_base = settings.STORAGE_LOCAL_PATH

        # 旧图片移入回收站
        if old_image_url and old_image_url.startswith("/storage/"):
            old_rel = old_image_url[len("/storage/"):]
            old_file = os.path.join(storage_base, old_rel.replace("/", os.sep))
            if await file_exists(old_file):
                try:
                    recycle_dir = os.path.join(storage_base, ".recycle")
                    await makedirs(recycle_dir, exist_ok=True)
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                    recycle_name = f"{ts}_{os.path.basename(old_file)}"
                    await move_file(old_file, os.path.join(recycle_dir, recycle_name))
                    logger.info(f"旧图片已移入回收站: {recycle_name}")
                except Exception as e:
                    logger.warning(f"移入回收站失败: {e}")

        # 下载新图片到本地
        try:
            entity_dir = os.path.join(storage_base, str(project_id), subdir, str(entity_id))
            await makedirs(entity_dir, exist_ok=True)

            filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.png"
            filepath = os.path.join(entity_dir, filename)

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(image_url, headers=_IMAGE_DOWNLOAD_HEADERS)
                resp.raise_for_status()
                await write_bytes_atomic(filepath, resp.content)

            local_path = f"/storage/{project_id}/{subdir}/{entity_id}/{filename}"
            logger.info(f"图片已保存到本地: {local_path}")
            return local_path
        except Exception as e:
            logger.warning(f"下载图片到本地失败，使用原始URL: {e}")
            return ""
