"""Character service - 人物IP service (migrated from app/services/character_service.py).

Implements short transaction pattern for AI calls: AI invocation does not hold
a DB session. Read -> close -> AI -> new session -> write.
"""
import asyncio
import base64
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.llm_utils import parse_llm_json
from app.infra.adapters.base_llm import ChatMessage
from app.infra.adapters.image_gen_adapter import ImageGenAdapter
from app.infra.adapters.http_client import HttpClientManager
from app.infra.adapters.llm_adapter import LLMAdapter
from app.infra.file_utils import (
    file_exists,
    makedirs,
    read_bytes,
    remove_file,
    write_bytes_atomic,
)
from app.models.character import (
    Character,
    CharacterState,
    CharacterOutfit,
    CharacterReferenceImage,
    CharacterRelation,
)
from app.repositories.character_repo import (
    CharacterOutfitRepository,
    CharacterReferenceImageRepository,
    CharacterRelationRepository,
    CharacterRepository,
)
from app.schemas.character_schema import (
    CharacterCreate,
    CharacterOutfitCreate,
    CharacterReferenceImageCreate,
    CharacterRelationCreate,
)
from app.infra.prompt_loader import get_prompt

logger = logging.getLogger(__name__)


class CharacterService:
    """人物IP服务 - handles character CRUD, relations, outfits, expressions,
    reference images, AI extraction and image generation.

    简单 CRUD 方法直接使用 self.session（由路由注入）。
    AI 方法（extract_characters_from_novel / generate_character_image）使用
    短事务模式：AI 调用期间不持有 DB session。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.char_repo = CharacterRepository(session)
        self.rel_repo = CharacterRelationRepository(session)
        self.outfit_repo = CharacterOutfitRepository(session)
        self.ref_img_repo = CharacterReferenceImageRepository(session)

    # =================================================================
    # 人物 CRUD
    # =================================================================

    async def create_character(self, project_id: UUID, data: CharacterCreate) -> Character:
        # 校验同一项目下角色名唯一
        existing = await self.session.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.name == data.name,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"角色姓名 '{data.name}' 已存在")
        return await self.char_repo.create(
            project_id=project_id, name=data.name, aliases="", description=""
        )

    async def get_character(self, character_id: UUID) -> Optional[Character]:
        return await self.char_repo.get(character_id)

    async def list_characters(
        self,
        project_id: UUID,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        role_type: Optional[str] = None,
    ) -> Tuple[List[Character], int]:
        """获取项目下的人物列表，支持按名称模糊搜索与角色类型过滤。"""
        filters = {"project_id": project_id}
        if role_type:
            filters["role_type"] = role_type
        if search:
            # 带搜索条件时手动构造查询（BaseRepository.list 不支持 ilike）
            query = select(Character).where(Character.project_id == project_id)
            count_query = select(func.count()).select_from(Character).where(
                Character.project_id == project_id
            )
            if role_type:
                query = query.where(Character.role_type == role_type)
                count_query = count_query.where(Character.role_type == role_type)
            query = query.where(Character.name.ilike(f"%{search}%"))
            count_query = count_query.where(Character.name.ilike(f"%{search}%"))
            total_result = await self.session.execute(count_query)
            total = total_result.scalar() or 0
            query = query.offset(skip).limit(limit).order_by(Character.created_at.desc())
            result = await self.session.execute(query)
            return list(result.scalars().all()), total
        return await self.char_repo.list(**filters, skip=skip, limit=limit)

    async def list_all_characters(
        self,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        role_type: Optional[str] = None,
        project_ids_query=None,
    ) -> Tuple[List[Character], int]:
        """获取所有项目的角色列表，支持按名称模糊搜索与角色类型过滤。

        Args:
            project_ids_query: SQLAlchemy select 子查询，用于限定项目范围（可选）
        """
        base_query = select(Character)
        count_query = select(func.count()).select_from(Character)

        conditions = []
        if project_ids_query is not None:
            conditions.append(Character.project_id.in_(project_ids_query))
        if role_type:
            conditions.append(Character.role_type == role_type)
        if search:
            conditions.append(Character.name.ilike(f"%{search}%"))

        if conditions:
            filter_clause = and_(*conditions)
            base_query = base_query.where(filter_clause)
            count_query = count_query.where(filter_clause)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        query = base_query.offset(skip).limit(limit).order_by(Character.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def update_character(self, character_id: UUID, data: dict) -> Optional[Character]:
        return await self.char_repo.update(character_id, **data)

    async def delete_character(self, character_id: UUID) -> bool:
        return await self.char_repo.delete(character_id)

    async def update_state(
        self, character_id: UUID, state_id: UUID, data: dict
    ) -> Optional[CharacterState]:
        """更新角色状态（名称/别名/描述/排序）。

        校验状态确实属于该角色，防止跨角色越权修改。
        """
        result = await self.session.execute(
            select(CharacterState).where(
                CharacterState.id == state_id,
                CharacterState.character_id == character_id,
            )
        )
        state = result.scalar_one_or_none()
        if state is None:
            return None
        for key, value in data.items():
            setattr(state, key, value)
        await self.session.flush()
        return state

    # =================================================================
    # 人物关系
    # =================================================================

    async def create_relation(
        self, project_id: UUID, character_id: UUID, data: CharacterRelationCreate
    ) -> CharacterRelation:
        return await self.rel_repo.create(
            project_id=project_id,
            character_a_id=character_id,
            character_b_id=data.character_b_id,
            relation_type_a_to_b=data.relation_type_a_to_b,
            relation_type_b_to_a=data.relation_type_b_to_a,
            description=data.description,
        )

    async def list_relations(self, character_id: UUID) -> List[CharacterRelation]:
        return await self.rel_repo.list_by_character(character_id)

    # =================================================================
    # 人物服装
    # =================================================================

    async def create_outfit(
        self, character_id: UUID, data: CharacterOutfitCreate
    ) -> CharacterOutfit:
        return await self.outfit_repo.create(
            character_id=character_id,
            name=data.name,
            outfit_type=data.outfit_type,
            description=data.description,
            color_scheme=data.color_scheme,
            scene_tags=data.scene_tags,
            reference_image_url=data.reference_image_url,
        )

    async def list_outfits(self, character_id: UUID) -> Tuple[List[CharacterOutfit], int]:
        """获取人物服装列表（全量，不做假分页）。"""
        items = await self.outfit_repo.list_all(character_id=character_id)
        return items, len(items)

    # =================================================================
    # 人物参考图
    # =================================================================

    async def create_reference_image(
        self, character_id: UUID, data: CharacterReferenceImageCreate
    ) -> CharacterReferenceImage:
        return await self.ref_img_repo.create(
            character_id=character_id,
            angle=data.angle,
            image_url=data.image_url,
            tags=data.tags,
        )

    async def list_reference_images(
        self, character_id: UUID
    ) -> Tuple[List[CharacterReferenceImage], int]:
        """获取人物参考图列表（全量，不做假分页）。"""
        items = await self.ref_img_repo.list_all(character_id=character_id)
        return items, len(items)

    # =================================================================
    # AI 方法（短事务模式）
    # =================================================================

    async def extract_characters_from_novel(
        self, project_id: UUID, novel_text: str
    ) -> List[Character]:
        """从小说文本中提取角色 — 短事务模式。

        Step 1: AI call（不持有 DB session）
        Step 2: Short write — 读取旧记录 -> 删除 -> 创建新记录 -> commit
        """
        if not novel_text:
            return []

        logger.info(f"===== 开始提取角色, novel_text长度={len(novel_text)} =====")

        # Step 1: AI call (no DB session held)
        llm = LLMAdapter(
            api_key=settings.LLM_API_KEY,
            api_base=settings.LLM_API_BASE,
            model=settings.LLM_MODEL or "gpt-4o",
        )
        system_prompt = await get_prompt("character_extraction")
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=novel_text),
        ]
        result = await llm.chat(messages, temperature=0.5)

        raw_content = result.content.strip()

        try:
            data = parse_llm_json(raw_content)
        except ValueError as e:
            logger.info(f"解析AI返回结果失败: {str(raw_content)}")
            # 临时：写入原始响应到txt便于调试
            try:
                from datetime import datetime
                tmp_path = rf"E:\VScode\Python\Comic Generation Engine\debug_llm_response_{datetime.now():%Y%m%d_%H%M%S}.txt"
                import pathlib
                pathlib.Path(tmp_path).write_text(raw_content, encoding="utf-8")
                logger.info(f"已将原始响应写入: {tmp_path}")
            except Exception as write_err:
                logger.warning(f"写入调试文件失败: {write_err}")
            raise ValueError(f"解析AI返回结果失败: {str(e)}")
            

        roles = data.get("roles", [])
        if not roles:
            return []

        # Step 2: Short write — read old + delete + create in independent session
        async with async_session_factory() as write_session:
            char_repo = CharacterRepository(write_session)

            # 保留旧角色的形象图（按名称映射），防止提取时丢失已生成的图片
            old_chars = await char_repo.list_all(project_id=project_id)
            old_image_map = {}
            for c in old_chars:
                ref_result = await write_session.execute(
                    select(CharacterReferenceImage).where(
                        CharacterReferenceImage.character_id == c.id,
                        CharacterReferenceImage.state_id.is_(None),
                    ).limit(1)
                )
                ref_img = ref_result.scalar_one_or_none()
                if ref_img:
                    old_image_map[c.name] = ref_img.image_url

            # 子表外键没有 ON DELETE CASCADE，表级 DELETE 也不触发 ORM 关系级联，
            # 必须先按 character_id 清空四张子表，否则外键约束会让整个事务回滚
            old_char_ids = select(Character.id).where(Character.project_id == project_id)
            await write_session.execute(
                CharacterReferenceImage.__table__.delete().where(
                    CharacterReferenceImage.character_id.in_(old_char_ids)
                )
            )
            await write_session.execute(
                CharacterState.__table__.delete().where(
                    CharacterState.character_id.in_(old_char_ids)
                )
            )
            await write_session.execute(
                CharacterOutfit.__table__.delete().where(
                    CharacterOutfit.character_id.in_(old_char_ids)
                )
            )
            await write_session.execute(
                CharacterRelation.__table__.delete().where(
                    or_(
                        CharacterRelation.character_a_id.in_(old_char_ids),
                        CharacterRelation.character_b_id.in_(old_char_ids),
                    )
                )
            )
            await write_session.execute(
                Character.__table__.delete().where(
                    Character.project_id == project_id
                )
            )

            created_characters = []

            for role in roles:
                name = role.get("name", "")
                aliases = role.get("aliases", "")
                description = role.get("description", "")

                character = await char_repo.create(
                    project_id=project_id,
                    name=name,
                    aliases=aliases,
                    description=description,
                )
                # 如果名称匹配旧记录，恢复形象图
                if name in old_image_map:
                    ref = CharacterReferenceImage(
                        character_id=character.id,
                        image_url=old_image_map[name],
                    )
                    write_session.add(ref)

                created_characters.append(character)

                # 处理角色的临时状态（state 为数组，支持多个状态）
                states = role.get("state")
                if states and isinstance(states, list):
                    for s in states:
                        state_name = s.get("name", f"{name}(临时状态)")
                        state_aliases = s.get("aliases", aliases)
                        state_description = s.get("description", "")

                        state_char = CharacterState(
                            character_id=character.id,
                            name=state_name,
                            aliases=state_aliases,
                            description=state_description,
                        )
                        # id 是列级默认值，必须先 flush 才能拿到，否则 state_id 会写成 NULL
                        # （NULL 在数据模型中表示"角色默认形象"）
                        write_session.add(state_char)
                        await write_session.flush()
                        # 如果该状态名匹配旧记录，恢复形象图
                        if state_name in old_image_map:
                            state_ref = CharacterReferenceImage(
                                character_id=character.id,
                                state_id=state_char.id,
                                image_url=old_image_map[state_name],
                            )
                            write_session.add(state_ref)

            await write_session.commit()
            return created_characters

    async def generate_character_image(
        self, character_id: UUID, project_id: UUID
    ) -> dict:
        """生成角色形象 — 短事务模式。

        Step 1: Short read — 获取角色数据（含父角色形象 URL）
        Step 2: File I/O — 读取父角色参考图（若有）
        Step 3: AI call — 调用图片生成（不持有 DB session）
        Step 4: File I/O — 下载并保存图片
        Step 5: Short write — 写入 CharacterReferenceImage 表
        """
        # Step 1: Short read transaction — get character data
        parent_img_url: Optional[str] = None
        parent_name: Optional[str] = None

        async with async_session_factory() as read_session:
            char_repo = CharacterRepository(read_session)
            character = await char_repo.get(character_id)
            if not character:
                raise ValueError("角色不存在")

            description = character.description or ""
            if not description:
                raise ValueError("角色描述为空")

            # 检查是否为角色状态（名称含括号）
            state_match = re.match(r"^(.+?)[（(]", character.name) if character.name else None
            character_name = character.name

            # 查询该角色的形象图 URL
            from app.models.character import CharacterReferenceImage as RefImage
            ref_result = await read_session.execute(
                select(RefImage).where(
                    RefImage.character_id == character_id,
                    RefImage.state_id.is_(None),
                ).limit(1)
            )
            ref_img = ref_result.scalar_one_or_none()
            old_image_url = ref_img.image_url if ref_img else ""

            if state_match:
                # 是角色状态，找父角色的默认形象作为参考图
                parent_name = state_match.group(1)
                result = await read_session.execute(
                    select(Character).where(
                        Character.project_id == project_id,
                        Character.name == parent_name,
                    )
                )
                parent_char = result.scalar_one_or_none()
                if parent_char:
                    parent_ref_result = await read_session.execute(
                        select(RefImage).where(
                            RefImage.character_id == parent_char.id,
                            RefImage.state_id.is_(None),
                        ).limit(1)
                    )
                    parent_ref_img = parent_ref_result.scalar_one_or_none()
                    if parent_ref_img:
                        parent_img_url = parent_ref_img.image_url
                    else:
                        raise ValueError(
                            f"请先生成角色「{parent_name}」的默认形象，再生成状态形象"
                        )
                else:
                    raise ValueError(
                        f"请先生成角色「{parent_name}」的默认形象，再生成状态形象"
                    )

        # Step 2: File I/O — read parent reference image (no DB session)
        parent_ref_image_b64: Optional[str] = None
        if parent_img_url and parent_img_url.startswith("/storage/"):
            storage_base = settings.STORAGE_LOCAL_PATH
            rel = parent_img_url[len("/storage/"):]
            file_path = os.path.join(storage_base, rel.replace("/", os.sep))
            img_bytes = await read_bytes(file_path)
            if img_bytes:
                parent_ref_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                logger.info(f"已加载父角色「{parent_name}」形象作为参考图")

        # Step 3: AI call (no DB session held)
        params = {"aspectRatio": "16:9"}
        if parent_ref_image_b64:
            params["images"] = [f"data:image/png;base64,{parent_ref_image_b64}"]

        image_gen = ImageGenAdapter()
        gen_result = await image_gen.generate(description, params=params)

        image_url = gen_result.get("image_url", "")
        local_path = ""

        if image_url:
            # Step 4: File I/O — download and save image
            storage_base = settings.STORAGE_LOCAL_PATH

            # 如果该角色已有本地图片，直接删除旧图
            if old_image_url.startswith("/storage/"):
                old_rel = old_image_url[len("/storage/"):]
                old_file = os.path.join(storage_base, old_rel.replace("/", os.sep))
                if await file_exists(old_file):
                    try:
                        await remove_file(old_file)
                        logger.info(f"旧形象已删除: {old_rel}")
                    except Exception as e:
                        logger.warning(f"删除旧形象失败: {e}")

            # 下载并保存新图片
            try:
                char_dir = os.path.join(
                    storage_base, str(project_id), "characters", str(character_id)
                )
                await makedirs(char_dir, exist_ok=True)

                filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.png"
                filepath = os.path.join(char_dir, filename)

                client = HttpClientManager.get_image_client()
                resp = await client.get(
                    image_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Referer": "https://grsai.dakka.com.cn/",
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                await write_bytes_atomic(filepath, resp.content)

                local_path = f"/storage/{project_id}/characters/{character_id}/{filename}"
                logger.info(f"角色形象已保存到本地: {local_path}")
            except Exception as e:
                logger.warning(f"下载角色形象到本地失败，使用原始URL: {e}")

            # Step 5: Short write transaction — save image to CharacterReferenceImage
            async with async_session_factory() as write_session:
                from app.models.character import CharacterReferenceImage as RefImg
                # 删除该角色的旧默认形象记录
                await write_session.execute(
                    RefImg.__table__.delete().where(
                        RefImg.character_id == character_id,
                        RefImg.state_id.is_(None),
                    )
                )
                # 创建新记录
                new_ref = RefImg(
                    character_id=character_id,
                    image_url=local_path or image_url,
                )
                write_session.add(new_ref)
                await write_session.commit()

        return {
            "character_id": str(character_id),
            "character_name": character_name,
            "image_url": local_path or image_url,
        }

    async def generate_state_image(
        self, character_id: UUID, state_id: UUID, project_id: UUID
    ) -> dict:
        """生成角色状态的专属形象 — 短事务模式。

        使用父角色的主图作为参考图，生成该状态的设定形象。
        """
        parent_img_url: Optional[str] = None
        parent_name: Optional[str] = None
        state_name: str = ""

        # Step 1: Short read — 获取状态数据及父角色形象
        async with async_session_factory() as read_session:
            from app.models.character import CharacterReferenceImage as RefImage

            # 查询状态记录
            state_result = await read_session.execute(
                select(CharacterState).where(CharacterState.id == state_id)
            )
            state = state_result.scalar_one_or_none()
            if not state:
                raise ValueError("角色状态不存在")

            state_name = state.name
            description = state.description or ""

            if not description:
                raise ValueError(f"状态「{state_name}」的描述为空，无法生成形象")

            # 查询父角色
            character = await read_session.execute(
                select(Character).where(Character.id == character_id)
            )
            character = character.scalar_one_or_none()
            if not character:
                raise ValueError("角色不存在")

            parent_name = character.name

            # 查询父角色的默认形象作为参考图
            parent_ref_result = await read_session.execute(
                select(RefImage).where(
                    RefImage.character_id == character_id,
                    RefImage.state_id.is_(None),
                ).limit(1)
            )
            parent_ref_img = parent_ref_result.scalar_one_or_none()
            if parent_ref_img:
                parent_img_url = parent_ref_img.image_url
            else:
                raise ValueError(
                    f"请先生成角色「{parent_name}」的默认形象，再生成状态形象"
                )

            # 查询旧的状态形象图（用于后续删除）
            old_ref_result = await read_session.execute(
                select(RefImage).where(
                    RefImage.character_id == character_id,
                    RefImage.state_id == state_id,
                ).limit(1)
            )
            old_ref_img = old_ref_result.scalar_one_or_none()
            old_image_url = old_ref_img.image_url if old_ref_img else ""

        # Step 2: File I/O — 读取父角色参考图
        parent_ref_image_b64: Optional[str] = None
        if parent_img_url and parent_img_url.startswith("/storage/"):
            storage_base = settings.STORAGE_LOCAL_PATH
            rel = parent_img_url[len("/storage/"):]
            file_path = os.path.join(storage_base, rel.replace("/", os.sep))
            img_bytes = await read_bytes(file_path)
            if img_bytes:
                parent_ref_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                logger.info(f"已加载父角色「{parent_name}」形象作为状态「{state_name}」的参考图")

        # Step 3: AI call — 生成图片
        params = {"aspectRatio": "16:9"}
        if parent_ref_image_b64:
            params["images"] = [f"data:image/png;base64,{parent_ref_image_b64}"]

        image_gen = ImageGenAdapter()
        gen_result = await image_gen.generate(description, params=params)

        image_url = gen_result.get("image_url", "")
        local_path = ""

        if image_url:
            # Step 4: File I/O — 下载并保存图片
            storage_base = settings.STORAGE_LOCAL_PATH

            # 删除旧状态图
            if old_image_url.startswith("/storage/"):
                old_rel = old_image_url[len("/storage/"):]
                old_file = os.path.join(storage_base, old_rel.replace("/", os.sep))
                if await file_exists(old_file):
                    try:
                        await remove_file(old_file)
                        logger.info(f"旧状态形象已删除: {old_rel}")
                    except Exception as e:
                        logger.warning(f"删除旧状态形象失败: {e}")

            # 下载并保存新图片
            try:
                # 保存到 characters/{character_id}/states/ 目录
                state_dir = os.path.join(
                    storage_base, str(project_id), "characters", str(character_id), "states"
                )
                await makedirs(state_dir, exist_ok=True)

                filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{state_id}.png"
                filepath = os.path.join(state_dir, filename)

                client = HttpClientManager.get_image_client()
                resp = await client.get(
                    image_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Referer": "https://grsai.dakka.com.cn/",
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                await write_bytes_atomic(filepath, resp.content)

                local_path = f"/storage/{project_id}/characters/{character_id}/states/{filename}"
                logger.info(f"状态形象已保存到本地: {local_path}")
            except Exception as e:
                logger.warning(f"下载状态形象到本地失败，使用原始URL: {e}")

            # Step 5: Short write — 写入 CharacterReferenceImage（关联 state_id）
            async with async_session_factory() as write_session:
                from app.models.character import CharacterReferenceImage as RefImg

                # 删除该状态旧的形象图记录
                await write_session.execute(
                    RefImg.__table__.delete().where(
                        RefImg.character_id == character_id,
                        RefImg.state_id == state_id,
                    )
                )
                # 创建新记录
                new_ref = RefImg(
                    character_id=character_id,
                    state_id=state_id,
                    image_url=local_path or image_url,
                )
                write_session.add(new_ref)
                await write_session.commit()

        return {
            "character_id": str(character_id),
            "state_id": str(state_id),
            "state_name": state_name,
            "image_url": local_path or image_url,
        }

    @staticmethod
    def cleanup_recycle_bin():
        """清理回收站中超过3天的文件"""
        storage_base = settings.STORAGE_LOCAL_PATH
        recycle_dir = os.path.join(storage_base, ".recycle")
        if not os.path.isdir(recycle_dir):
            return

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=3)
        count = 0
        for fname in os.listdir(recycle_dir):
            fpath = os.path.join(recycle_dir, fname)
            if os.path.isfile(fpath):
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)
                if mtime < cutoff:
                    os.remove(fpath)
                    count += 1
        if count:
            logger.info(f"回收站清理: 已删除 {count} 个过期文件")
