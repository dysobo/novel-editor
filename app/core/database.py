import sqlite3
import json
import os
from datetime import datetime


class Database:
    def __init__(self, db_path: str):
        self._path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER DEFAULT NULL,
                title TEXT NOT NULL DEFAULT '未命名章节',
                content TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (parent_id) REFERENCES chapters(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                avatar_path TEXT DEFAULT '',
                profile TEXT DEFAULT '{}',
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS world_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT '通用',
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS outlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER DEFAULT NULL,
                level TEXT DEFAULT 'chapter',
                title TEXT NOT NULL DEFAULT '',
                content TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS ai_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER,
                summary TEXT DEFAULT '',
                key_events TEXT DEFAULT '[]',
                character_changes TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
            );
        """)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ── 章节 CRUD ──
    def add_chapter(self, title="未命名章节", parent_id=None, sort_order=0):
        cur = self._conn.execute(
            "INSERT INTO chapters (title, parent_id, sort_order) VALUES (?, ?, ?)",
            (title, parent_id, sort_order),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_chapters(self, parent_id=None):
        if parent_id is None:
            return self._conn.execute(
                "SELECT * FROM chapters WHERE parent_id IS NULL ORDER BY sort_order"
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM chapters WHERE parent_id=? ORDER BY sort_order",
            (parent_id,),
        ).fetchall()

    def get_chapter(self, chapter_id):
        return self._conn.execute(
            "SELECT * FROM chapters WHERE id=?", (chapter_id,)
        ).fetchone()

    def update_chapter(self, chapter_id, **kwargs):
        allowed = {"title", "content", "parent_id", "sort_order", "word_count"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [chapter_id]
        self._conn.execute(f"UPDATE chapters SET {sets} WHERE id=?", vals)
        self._conn.commit()

    def delete_chapter(self, chapter_id):
        self._conn.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
        self._conn.commit()

    def move_chapter(self, chapter_id, new_parent_id, new_sort_order):
        self.update_chapter(chapter_id, parent_id=new_parent_id, sort_order=new_sort_order)

    # ── 角色 CRUD ──
    def add_character(self, name, description="", profile=None):
        profile_json = json.dumps(profile or {}, ensure_ascii=False)
        cur = self._conn.execute(
            "INSERT INTO characters (name, description, profile) VALUES (?, ?, ?)",
            (name, description, profile_json),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_characters(self):
        return self._conn.execute(
            "SELECT * FROM characters ORDER BY created_at"
        ).fetchall()

    def get_character(self, char_id):
        return self._conn.execute(
            "SELECT * FROM characters WHERE id=?", (char_id,)
        ).fetchone()

    def update_character(self, char_id, **kwargs):
        allowed = {"name", "description", "profile", "avatar_path"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if "profile" in fields and isinstance(fields["profile"], dict):
            fields["profile"] = json.dumps(fields["profile"], ensure_ascii=False)
        if not fields:
            return
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [char_id]
        self._conn.execute(f"UPDATE characters SET {sets} WHERE id=?", vals)
        self._conn.commit()

    def delete_character(self, char_id):
        self._conn.execute("DELETE FROM characters WHERE id=?", (char_id,))
        self._conn.commit()

    # ── 世界观 CRUD ──
    def add_world_setting(self, title, category="通用", content=""):
        cur = self._conn.execute(
            "INSERT INTO world_settings (title, category, content) VALUES (?, ?, ?)",
            (title, category, content),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_world_settings(self, category=None):
        if category:
            return self._conn.execute(
                "SELECT * FROM world_settings WHERE category=? ORDER BY sort_order",
                (category,),
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM world_settings ORDER BY category, sort_order"
        ).fetchall()

    def update_world_setting(self, setting_id, **kwargs):
        allowed = {"title", "category", "content", "sort_order"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [setting_id]
        self._conn.execute(f"UPDATE world_settings SET {sets} WHERE id=?", vals)
        self._conn.commit()

    def delete_world_setting(self, setting_id):
        self._conn.execute("DELETE FROM world_settings WHERE id=?", (setting_id,))
        self._conn.commit()

    # ── 大纲 CRUD ──
    def add_outline(self, title, level="chapter", parent_id=None, content=""):
        cur = self._conn.execute(
            "INSERT INTO outlines (title, level, parent_id, content) VALUES (?, ?, ?, ?)",
            (title, level, parent_id, content),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_outlines(self, parent_id=None):
        if parent_id is None:
            return self._conn.execute(
                "SELECT * FROM outlines WHERE parent_id IS NULL ORDER BY sort_order"
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM outlines WHERE parent_id=? ORDER BY sort_order",
            (parent_id,),
        ).fetchall()

    def update_outline(self, outline_id, **kwargs):
        allowed = {"title", "level", "content", "parent_id", "sort_order"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sets = ", ".join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [outline_id]
        self._conn.execute(f"UPDATE outlines SET {sets} WHERE id=?", vals)
        self._conn.commit()

    def delete_outline(self, outline_id):
        self._conn.execute("DELETE FROM outlines WHERE id=?", (outline_id,))
        self._conn.commit()

    # ── AI 记忆 CRUD ──
    def save_ai_memory(self, chapter_id, summary, key_events=None, character_changes=None):
        events_json = json.dumps(key_events or [], ensure_ascii=False)
        changes_json = json.dumps(character_changes or {}, ensure_ascii=False)
        existing = self._conn.execute(
            "SELECT id FROM ai_memory WHERE chapter_id=?", (chapter_id,)
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE ai_memory SET summary=?, key_events=?, character_changes=? WHERE chapter_id=?",
                (summary, events_json, changes_json, chapter_id),
            )
        else:
            self._conn.execute(
                "INSERT INTO ai_memory (chapter_id, summary, key_events, character_changes) VALUES (?, ?, ?, ?)",
                (chapter_id, summary, events_json, changes_json),
            )
        self._conn.commit()

    def get_ai_memory(self, chapter_id):
        return self._conn.execute(
            "SELECT * FROM ai_memory WHERE chapter_id=?", (chapter_id,)
        ).fetchone()

    def get_all_ai_memories(self):
        return self._conn.execute(
            "SELECT am.*, c.title as chapter_title FROM ai_memory am "
            "LEFT JOIN chapters c ON am.chapter_id = c.id ORDER BY am.chapter_id"
        ).fetchall()

    def get_world_categories(self):
        rows = self._conn.execute(
            "SELECT DISTINCT category FROM world_settings ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]
