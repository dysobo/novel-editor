import os
import shutil
from app.core.database import Database


class Project:
    def __init__(self, path: str, db: Database):
        self.path = path
        self.db = db
        self.name = os.path.splitext(os.path.basename(path))[0]

    @classmethod
    def create(cls, path: str) -> "Project":
        """新建项目（.novel 实际上是 SQLite 数据库文件）"""
        if os.path.exists(path):
            os.remove(path)
        db = Database(path)
        project = cls(path, db)
        # 创建默认卷和章节
        vol_id = db.add_chapter("第一卷", parent_id=0, sort_order=0)
        db.add_chapter("第一章", parent_id=vol_id, sort_order=0)
        return project

    @classmethod
    def open(cls, path: str) -> "Project":
        """打开已有项目"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"项目文件不存在: {path}")
        db = Database(path)
        return cls(path, db)

    def save(self):
        """显式保存（SQLite 自动提交，这里做 WAL checkpoint）"""
        self.db._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self):
        self.db.close()
