from typing import Generic, TypeVar, Optional, List, Type, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update as sa_update
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get(self, id: UUID, options: Optional[List] = None) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        if options:
            stmt = stmt.options(*options)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 20, order_by: Any = None,
        options: Optional[List] = None, **filters
    ) -> tuple[List[ModelType], int]:
        query = select(self.model)
        if options:
            query = query.options(*options)
        count_query = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
                count_query = count_query.where(getattr(self.model, key) == value)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.created_at.desc())
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def list_all(
        self, cap: int = 5000, order_by: Any = None,
        options: Optional[List] = None, **filters
    ) -> List[ModelType]:
        """返回所有匹配记录（无分页）。仅用于内部业务逻辑。

        cap 防止滥用导致内存爆炸。如确实需要更多，调用方显式传更大值。
        """
        query = select(self.model)
        if options:
            query = query.options(*options)
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        if order_by is not None:
            query = query.order_by(order_by)
        else:
            query = query.order_by(self.model.created_at.desc())
        query = query.limit(cap)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, id: UUID, **kwargs) -> Optional[ModelType]:
        values = {k: v for k, v in kwargs.items() if hasattr(self.model, k)}
        if not values:
            return await self.get(id)
        stmt = (
            sa_update(self.model)
            .where(self.model.id == id)
            .values(**values)
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(id)

    async def update_if(
        self,
        id: UUID,
        conditions: dict,
        **kwargs,
    ) -> bool:
        """带条件的原子 UPDATE，用于乐观锁/状态机转换。

        conditions 中 value 为元组时按 IN 处理。返回是否实际更新了一行。
        """
        stmt = sa_update(self.model).where(self.model.id == id)
        for k, v in conditions.items():
            col = getattr(self.model, k)
            if isinstance(v, (tuple, list)):
                stmt = stmt.where(col.in_(v))
            else:
                stmt = stmt.where(col == v)
        values = {k: v for k, v in kwargs.items() if hasattr(self.model, k)}
        if not values:
            return False
        stmt = stmt.values(**values)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def delete(self, id: UUID) -> bool:
        instance = await self.get(id)
        if instance:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False
