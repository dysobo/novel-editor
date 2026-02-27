import json
from app.core.database import Database


class MemoryManager:
    """三层记忆架构：全局锚定层 + 滚动摘要层 + 近章原文层"""

    def __init__(self, db: Database):
        self.db = db

    def build_context(self, current_chapter_id: int = None) -> list:
        """组装完整的记忆上下文，返回 messages 列表"""
        messages = []

        # 第一层：全局锚定层 (~1000 token)
        anchor = self._build_anchor_layer()
        if anchor:
            messages.append({"role": "system", "content": anchor})

        # 第二层：滚动摘要层 (~2000 token)
        summary = self._build_summary_layer(current_chapter_id)
        if summary:
            messages.append({"role": "system", "content": summary})

        # 第三层：近章原文层 (~4000 token)
        recent = self._build_recent_layer(current_chapter_id)
        if recent:
            messages.append({"role": "system", "content": recent})

        return messages

    def _build_anchor_layer(self) -> str:
        """全局锚定层：角色档案 + 世界观 + 总大纲"""
        parts = []

        # 角色档案
        characters = self.db.get_characters()
        if characters:
            char_lines = []
            for c in characters:
                char_lines.append(f"- {c['name']}: {c['description'] or '无描述'}")
            parts.append("【主要角色】\n" + "\n".join(char_lines))

        # 世界观设定
        settings = self.db.get_world_settings()
        if settings:
            ws_lines = []
            for s in settings:
                ws_lines.append(f"- [{s['category']}] {s['title']}: {s['content'][:100]}")
            parts.append("【世界观】\n" + "\n".join(ws_lines))

        # 总大纲
        outlines = self.db.get_outlines(0)
        if outlines:
            ol_lines = []
            for o in outlines:
                ol_lines.append(f"- [{o['level']}] {o['title']}: {o['content'][:100]}")
            parts.append("【大纲】\n" + "\n".join(ol_lines))

        return "\n\n".join(parts) if parts else ""

    def _build_summary_layer(self, current_chapter_id: int = None) -> str:
        """滚动摘要层：已完成章节的摘要 + 关键事件 + 角色状态变化"""
        memories = self.db.get_all_ai_memories()
        if not memories:
            return ""
        parts = ["【前情摘要】"]
        for m in memories:
            if current_chapter_id and m["chapter_id"] >= current_chapter_id:
                continue
            title = m["chapter_title"] or f"章节{m['chapter_id']}"
            parts.append(f"\n{title}:")
            parts.append(f"  摘要: {m['summary']}")
            try:
                events = json.loads(m["key_events"] or "[]")
                if events:
                    parts.append(f"  关键事件: {', '.join(events)}")
            except json.JSONDecodeError:
                pass
            try:
                changes = json.loads(m["character_changes"] or "{}")
                if changes:
                    change_strs = [f"{k}: {v}" for k, v in changes.items()]
                    parts.append(f"  角色变化: {'; '.join(change_strs)}")
            except json.JSONDecodeError:
                pass
        return "\n".join(parts) if len(parts) > 1 else ""

    def _build_recent_layer(self, current_chapter_id: int = None) -> str:
        """近章原文层：最近 2-3 章的完整内容"""
        if not current_chapter_id:
            return ""
        # 获取所有章节，按 sort_order 排列，找到当前章节之前的 2-3 章
        all_chapters = self._get_all_chapters_flat()
        current_idx = None
        for i, ch in enumerate(all_chapters):
            if ch["id"] == current_chapter_id:
                current_idx = i
                break
        if current_idx is None or current_idx == 0:
            return ""
        start = max(0, current_idx - 3)
        recent = all_chapters[start:current_idx]
        parts = ["【近章原文】"]
        for ch in recent:
            if ch["content"]:
                # 去除 HTML 标签的简单处理
                import re
                text = re.sub(r'<[^>]+>', '', ch["content"])
                text = text.strip()
                if text:
                    parts.append(f"\n--- {ch['title']} ---\n{text[:2000]}")
        return "\n".join(parts) if len(parts) > 1 else ""

    def _get_all_chapters_flat(self) -> list:
        """递归获取所有章节，按树形顺序展平"""
        result = []
        self._flatten(0, result)
        return result

    def _flatten(self, parent_id, result):
        chapters = self.db.get_chapters(parent_id)
        for ch in chapters:
            result.append(dict(ch))
            self._flatten(ch["id"], result)
