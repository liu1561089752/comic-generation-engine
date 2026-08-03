#!/usr/bin/env python
"""备份数据库所有表数据为 JSON 文件。"""
import json
import os
from datetime import datetime

from sqlalchemy import create_engine, inspect, text

# 从 alembic.ini 读取的数据库连接
DB_URL = "postgresql://postgres:854223@localhost:5432/webtoon_factory"

engine = create_engine(DB_URL)
inspector = inspect(engine)

BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "db_backup")
os.makedirs(BACKUP_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.json")

all_data = {}

with engine.connect() as conn:
    # 按依赖顺序导出（先导出无外键依赖的表）
    table_names = inspector.get_table_names()
    # alembic_version 表不需要
    table_names = [t for t in table_names if t != "alembic_version"]

    for table_name in table_names:
        result = conn.execute(text(f"SELECT * FROM {table_name} ORDER BY 1"))
        rows = []
        for row in result.mappings():
            # 将 datetime/UUID 对象转为字符串
            serializable = {}
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    serializable[k] = v.isoformat()
                else:
                    serializable[k] = str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            rows.append(serializable)
        all_data[table_name] = rows
        print(f"  表 {table_name}: {len(rows)} 行")

with open(backup_file, "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print(f"\n备份完成: {backup_file}")
print(f"总计 {len(all_data)} 张表")
engine.dispose()
