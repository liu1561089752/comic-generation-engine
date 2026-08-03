#!/usr/bin/env python
"""删除并重建数据库。"""
import sys

from sqlalchemy import create_engine, text

# 连接到 postgres 默认数据库（不能连目标库，因为要 DROP）
ADMIN_DB_URL = "postgresql://postgres:854223@localhost:5432/postgres"
TARGET_DB = "webtoon_factory"

engine = create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")

with engine.connect() as conn:
    # 终止所有连接到目标库的连接
    conn.execute(text(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{TARGET_DB}'
          AND pid <> pg_backend_pid()
    """))
    print(f"已终止 {TARGET_DB} 的所有连接")

    # 删除数据库
    conn.execute(text(f"DROP DATABASE IF EXISTS {TARGET_DB}"))
    print(f"已删除数据库 {TARGET_DB}")

    # 重建数据库
    conn.execute(text(f"CREATE DATABASE {TARGET_DB}"))
    print(f"已创建数据库 {TARGET_DB}")

engine.dispose()
print("完成！")
