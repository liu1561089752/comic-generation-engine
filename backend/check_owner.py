"""检查项目归属"""
import asyncio
from app.core.database import async_session_factory
from app.models.novel import Project
from app.models.user import User
from sqlalchemy import select


async def q():
    async with async_session_factory() as s:
        r = await s.execute(select(Project.id, Project.name, Project.user_id))
        print("=== 项目 ===")
        for row in r:
            print(f"  {row.id} | {row.name} | user_id={row.user_id}")

        r2 = await s.execute(select(User.id, User.username))
        print("\n=== 用户 ===")
        for row in r2:
            print(f"  {row.id} | {row.username}")


asyncio.run(q())
