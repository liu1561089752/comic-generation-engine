"""临时脚本：打印第一章节发往 AI 的提示词数据（直接用 asyncpg 避免 SQLAlchemy 连接问题）。"""
import asyncio
import json

import asyncpg


async def main():
    conn = await asyncpg.connect(
        user="postgres", password="854223",
        host="localhost", port=5432, database="webtoon_factory"
    )
    try:
        # 1. 获取第一部小说
        novel_row = await conn.fetchrow(
            "SELECT id, title FROM novels ORDER BY created_at LIMIT 1"
        )
        if not novel_row:
            print("数据库中没有小说数据")
            return
        novel_id = novel_row["id"]
        print(f"小说: {novel_row['title']} (id={novel_id})")

        # 2. 获取第一章排版章节
        lc = await conn.fetchrow(
            "SELECT id, title, sort_order FROM layout_chapters "
            "WHERE novel_id = $1 ORDER BY sort_order LIMIT 1",
            novel_id
        )
        if not lc:
            print("没有排版章节数据")
            return
        print(f"\n排版章节: {lc['title']} (sort_order={lc['sort_order']})")
        sort_order = lc["sort_order"]

        # 3. 获取该章节的所有页面
        pages = await conn.fetch(
            "SELECT id, page_id, layout_type, page_purpose, visual_focus, sort_order "
            "FROM layout_pages WHERE chapter_id = $1 ORDER BY sort_order",
            lc["id"]
        )
        if not pages:
            print("该章节没有页面")
            return

        page_ids = [p["id"] for p in pages]
        # 获取 LayoutShot
        layout_shots = await conn.fetch(
            "SELECT id, page_id, shot_id, sort_order FROM layout_shots "
            "WHERE page_id = ANY($1) ORDER BY sort_order",
            page_ids
        )
        shot_map: dict = {}
        for ls in layout_shots:
            shot_map.setdefault(str(ls["page_id"]), []).append(ls)

        # 4. 查询 ScriptShot.content
        sc = await conn.fetchrow(
            "SELECT id FROM script_chapters "
            "WHERE novel_id = $1 AND sort_order = $2 LIMIT 1",
            novel_id, sort_order
        )
        content_map = {}
        if sc:
            ss_rows = await conn.fetch(
                "SELECT shot_id, content FROM script_shots WHERE chapter_id = $1",
                sc["id"]
            )
            for ss in ss_rows:
                content_map[ss["shot_id"]] = ss["content"]

        # 5. 查询 StoryboardShot.storyboard_details
        sbc = await conn.fetchrow(
            "SELECT id FROM storyboard_chapters "
            "WHERE novel_id = $1 AND sort_order = $2 LIMIT 1",
            novel_id, sort_order
        )
        sb_detail_map = {}
        if sbc:
            sbs_rows = await conn.fetch(
                "SELECT shot_id, storyboard_details FROM storyboard_shots WHERE chapter_id = $1",
                sbc["id"]
            )
            for sbs in sbs_rows:
                sb_detail_map[sbs["shot_id"]] = sbs["storyboard_details"]

        # 6. 构建页面列表，每个页面嵌入完整的 shot 数据
        payload = []
        for p in pages:
            ls_list = shot_map.get(str(p["id"]), [])
            page_shots = []
            for ls in ls_list:
                sid = ls["shot_id"]
                page_shots.append({
                    "shotId": sid,
                    "content": content_map.get(sid, ""),
                    "storyboardDetails": sb_detail_map.get(sid, ""),
                })
            payload.append({
                "pageId": p["page_id"],
                "layoutType": p["layout_type"],
                "pagePurpose": p["page_purpose"],
                "visualFocus": p["visual_focus"],
                "shots": page_shots,
            })

        print(f"\n章节页面数: {len(pages)}")
        print(f"\n{'='*60}")
        print("发送给 AI 的 payload:")
        print(f"{'='*60}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
