import json
import logging
import secrets

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


logger = logging.getLogger(__name__)


def _json_serializer(obj):
    return json.dumps(obj, ensure_ascii=False)


# PostgreSQL 统一引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    json_serializer=_json_serializer,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库：创建默认管理员用户。

    表结构通过 Alembic 迁移管理，此处不再用 create_all。
    """
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from app.models.user import User
    from app.core.security import hash_password

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none() is None:
            if settings.APP_ENV == "production":
                if not settings.ADMIN_INITIAL_PASSWORD:
                    raise ValueError(
                        "生产环境必须在 .env 中设置 ADMIN_INITIAL_PASSWORD"
                    )
                initial_password = settings.ADMIN_INITIAL_PASSWORD
            else:
                initial_password = settings.ADMIN_INITIAL_PASSWORD or secrets.token_urlsafe(12)
            admin_user = User(
                username="admin",
                password_hash=hash_password(initial_password),
                email="admin@example.com",
                is_admin=True,
            )
            session.add(admin_user)
            try:
                await session.commit()
            except IntegrityError:
                # 多 worker 首次启动时会同时 INSERT，后到者撞 username 唯一约束，
                # 视为已由其他 worker 创建，避免异常从 lifespan 冒出导致启动失败
                await session.rollback()
                logger.info("默认管理员用户已由其他进程创建，跳过初始化")
                return
            logger.info("已创建默认管理员用户 (admin)")
            if settings.APP_ENV == "development" and not settings.ADMIN_INITIAL_PASSWORD:
                logger.info(f"开发环境随机初始密码: {initial_password}（请在 .env 设置 ADMIN_INITIAL_PASSWORD 以固定密码）")
