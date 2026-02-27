import json
from app.ai.client import AIClient
from app.ai.memory import MemoryManager
from app.ai.prompts import (
    SYSTEM_BASE, CONTINUE_PROMPT, POLISH_PROMPT,
    SUMMARY_PROMPT, OUTLINE_PROMPT,
    GENERATE_OUTLINE_PROMPT, WRITE_CHAPTER_PROMPT,
)
from app.core.database import Database


class AITasks:
    def __init__(self, client: AIClient, db: Database):
        self.client = client
        self.memory = MemoryManager(db)
        self.db = db

    def continue_writing(self, content: str, chapter_id: int = None):
        """续写 - 流式输出"""
        context_msgs = self.memory.build_context(chapter_id)
        messages = [{"role": "system", "content": SYSTEM_BASE}]
        messages.extend(context_msgs)
        messages.append({
            "role": "user",
            "content": CONTINUE_PROMPT.format(content=content[-3000:]),
        })
        return self.client.chat_stream(messages)

    def polish(self, content: str):
        """润色 - 流式输出"""
        messages = [
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user", "content": POLISH_PROMPT.format(content=content)},
        ]
        return self.client.chat_stream(messages)

    def generate_summary(self, content: str, title: str, chapter_id: int):
        """生成章节摘要并存入数据库"""
        messages = [
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user", "content": SUMMARY_PROMPT.format(
                title=title, content=content[:4000]
            )},
        ]
        result = self.client.chat(messages)
        try:
            data = json.loads(result)
            self.db.save_ai_memory(
                chapter_id,
                summary=data.get("summary", ""),
                key_events=data.get("key_events", []),
                character_changes=data.get("character_changes", {}),
            )
            return data
        except json.JSONDecodeError:
            self.db.save_ai_memory(chapter_id, summary=result[:200])
            return {"summary": result[:200], "key_events": [], "character_changes": {}}

    def generate_outline(self, context_info: str):
        """生成大纲 - 流式输出"""
        messages = [
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user", "content": OUTLINE_PROMPT.format(context=context_info)},
        ]
        return self.client.chat_stream(messages)

    def generate_full_outline(self, title: str, genre: str, idea: str):
        """根据设定生成完整大纲 - 返回文本"""
        extra = ""
        characters = self.db.get_characters()
        if characters:
            lines = [f"- {c['name']}: {c['description'] or '无描述'}" for c in characters]
            extra += "已有角色：\n" + "\n".join(lines) + "\n\n"
        settings = self.db.get_world_settings()
        if settings:
            lines = [f"- {s['title']}: {s['content'][:80]}" for s in settings]
            extra += "世界观设定：\n" + "\n".join(lines) + "\n\n"
        messages = [
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user", "content": GENERATE_OUTLINE_PROMPT.format(
                title=title, genre=genre, idea=idea, extra_context=extra
            )},
        ]
        return self.client.chat(messages, max_tokens=4000)

    def write_chapter(self, title: str, outline: str, chapter_id: int = None):
        """根据大纲写一章内容 - 流式输出"""
        context_msgs = self.memory.build_context(chapter_id)
        messages = [{"role": "system", "content": SYSTEM_BASE}]
        messages.extend(context_msgs)
        messages.append({
            "role": "user",
            "content": WRITE_CHAPTER_PROMPT.format(title=title, outline=outline),
        })
        return self.client.chat_stream(messages, max_tokens=4000)
