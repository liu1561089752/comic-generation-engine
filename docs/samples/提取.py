import sqlite3
import json
import os
import sys

def main():
    db_path = "app.db"
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件 '{db_path}' 不存在，请将文件放在当前目录。")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='layout_pages'")
    if not cursor.fetchone():
        print("❌ 表 'layout_pages' 不存在，请检查数据库结构。")
        sys.exit(1)

    # 查询所有页面（按 sort_order 排序，若无则可不排序）
    cursor.execute("SELECT page_id, shots FROM layout_pages ORDER BY sort_order")
    rows = cursor.fetchall()
    conn.close()

    mapping = {}
    for row in rows:
        page_id = row["page_id"]          # 可能是整数或字符串
        shots_str = row["shots"]
        if not shots_str:
            continue

        try:
            shots = json.loads(shots_str)  # 尝试解析为 JSON
            # 处理两种可能：数组或单个对象
            if isinstance(shots, list) and shots:
                first_shot = shots[0]
            elif isinstance(shots, dict):
                first_shot = shots
            else:
                continue

            shot_id = first_shot.get("shotId")
            if shot_id:
                # 将 page_id 转换为字符串，并统一加上 "P" 前缀
                page_key = f"P{page_id}" if not str(page_id).startswith('P') else str(page_id)
                mapping[shot_id] = page_key
        except json.JSONDecodeError:
            # 如果 shots 不是合法 JSON，尝试通过正则提取第一个 shotId（备选）
            import re
            match = re.search(r'"shotId"\s*:\s*"([^"]+)"', shots_str)
            if match:
                shot_id = match.group(1)
                page_key = f"P{page_id}" if not str(page_id).startswith('P') else str(page_id)
                mapping[shot_id] = page_key
            else:
                print(f"⚠️ 无法解析 page_id={page_id} 的 shots 字段")

    # 保存映射为 JSON 文件
    output_file = "shot_page_map.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"✅ 已生成 {output_file}，共 {len(mapping)} 条映射。")

if __name__ == "__main__":
    main()