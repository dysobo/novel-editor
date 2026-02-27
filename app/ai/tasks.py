import json
from app.ai.client import AIClient
from app.ai.memory import MemoryManager
from app.ai.prompts import (
    SYSTEM_BASE, CONTINUE_PROMPT, POLISH_PROMPT,
    SUMMARY_PROMPT, OUTLINE_PROMPT,
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
