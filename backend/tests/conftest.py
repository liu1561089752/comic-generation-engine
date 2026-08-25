"""pytest 公共替身：FakeResult / FakeDB（按 SQL 主表返回预设值）。"""
import re


class FakeResult:
    """模拟 AsyncSession.execute 的返回对象。

    scalar() 对 0/None 统一返回 None：存在性检查（is not None）判为不存在，
    count 查询（.scalar() or 0）仍得 0。
    """

    def __init__(self, value=None):
        self._value = value
        self.rowcount = 1 if value not in (None, 0) else 0

    def scalar(self):
        return self._value if self._value not in (None, 0) else None

    def scalar_one_or_none(self):
        return self._value if self._value not in (None, 0) else None

    def all(self):
        return []

    def scalars(self):
        class _Scalars:
            def all(self):
                return []
        return _Scalars()


def _main_table(sql: str) -> str:
    """取 SQL 主查询第一个 FROM 子句的表名（忽略子查询）。"""
    m = re.search(r"\bfrom\s+([a-z_0-9\"`']+)", sql)
    if not m:
        return ""
    return m.group(1).strip('"`\'')


class FakeDB:
    """按 SQL 主表名返回预设值的假 session。

    counts: {主表名: int 或 {"total": int, "with_img": int}}
    - int：任何匹配该表的查询都返回此值
    - dict：SQL 含 "image_url"（有图条件）时返回 with_img，否则返回 total
    """

    def __init__(self, counts: dict):
        self.counts = counts

    def _resolve(self, key: str, sql: str):
        entry = self.counts[key]
        if isinstance(entry, dict):
            return entry["with_img"] if "image_url" in sql else entry["total"]
        return entry

    async def execute(self, stmt, *args, **kwargs):
        sql = str(stmt.compile()).lower()
        # O14: 四类资产计数合并为 UNION ALL 查询（SQL 同时含 scene_assets 等表名），
        # 用预设的 _assets_union 键返回合计值（有图条件按 image_url 区分）
        if "union all" in sql and "scene_assets" in sql:
            entry = self.counts.get("_assets_union")
            if isinstance(entry, dict):
                return FakeResult(entry["with_img"] if "image_url" in sql else entry["total"])
        main = _main_table(sql)
        if main and main in self.counts:
            return FakeResult(self._resolve(main, sql))
        # 回退：全 SQL 关键词匹配（长度优先，覆盖子查询表）
        for key in sorted(self.counts, key=len, reverse=True):
            if key in sql:
                return FakeResult(self._resolve(key, sql))
        return FakeResult(0)
