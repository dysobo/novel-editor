from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QTextEdit, QLineEdit, QInputDialog,
    QMessageBox, QComboBox, QSplitter, QFormLayout,
)
from PySide6.QtCore import Qt


class OutlinePanel(QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self._current_id = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("大纲")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Vertical)

        # 上半：大纲树
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        self.level_combo = QComboBox()
        self.level_combo.addItems(["总纲", "卷纲", "章纲"])
        btn_add = QPushButton("+ 添加")
        btn_del = QPushButton("删除")
        btn_add.clicked.connect(self._add_outline)
        btn_del.clicked.connect(self._delete_outline)
        btn_layout.addWidget(self.level_combo)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        top_layout.addLayout(btn_layout)

        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderLabel("大纲结构")
        self.outline_tree.setDragDropMode(QTreeWidget.InternalMove)
        self.outline_tree.currentItemChanged.connect(self._on_select)
        top_layout.addWidget(self.outline_tree)
        splitter.addWidget(top)

        # 下半：编辑区
        bottom = QWidget()
        form = QFormLayout(bottom)
        self.title_edit = QLineEdit()
        form.addRow("标题:", self.title_edit)
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("大纲内容...")
        form.addRow("内容:", self.content_edit)
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save_outline)
        form.addRow(btn_save)
        splitter.addWidget(bottom)

        layout.addWidget(splitter)

    def set_project(self, project):
        self.project = project
        self.reload()

    def reload(self):
        self.outline_tree.clear()
        self._current_id = None
        self.title_edit.clear()
        self.content_edit.clear()
        if not self.project:
            return
        self._load_children(0, self.outline_tree.invisibleRootItem())
        self.outline_tree.expandAll()

    def _load_children(self, parent_id, parent_item):
        outlines = self.project.db.get_outlines(parent_id)
        for o in outlines:
            level_map = {"main": "总纲", "volume": "卷纲", "chapter": "章纲"}
            label = f"[{level_map.get(o['level'], o['level'])}] {o['title']}"
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, o["id"])
            parent_item.addChild(item)
            self._load_children(o["id"], item)

    def _on_select(self, current, previous):
        if not current or not self.project:
            return
        oid = current.data(0, Qt.UserRole)
        self._current_id = oid
        outlines = self.project.db.get_outlines()
        # 递归查找
        self._fill_from_db(oid)

    def _fill_from_db(self, oid):
        """从数据库加载大纲详情到编辑区"""
        # 简单遍历所有大纲查找
        conn = self.project.db._conn
        row = conn.execute("SELECT * FROM outlines WHERE id=?", (oid,)).fetchone()
        if row:
            self.title_edit.setText(row["title"])
            self.content_edit.setPlainText(row["content"] or "")

    def _add_outline(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先通过 文件→新建项目 或 文件→打开项目 创建/打开一个项目")
            return
        level_map = {"总纲": "main", "卷纲": "volume", "章纲": "chapter"}
        level = level_map.get(self.level_combo.currentText(), "chapter")
        title, ok = QInputDialog.getText(self, "新建大纲", "大纲标题:")
        if ok and title:
            parent_id = 0
            current = self.outline_tree.currentItem()
            if current:
                parent_id = current.data(0, Qt.UserRole) or 0
            self.project.db.add_outline(title, level=level, parent_id=parent_id)
            self.reload()

    def _delete_outline(self):
        if not self.project or self._current_id is None:
            return
        ret = QMessageBox.question(self, "确认", "确定删除该大纲？")
        if ret == QMessageBox.Yes:
            self.project.db.delete_outline(self._current_id)
            self.reload()

    def _save_outline(self):
        if not self.project or self._current_id is None:
            return
        self.project.db.update_outline(
            self._current_id,
            title=self.title_edit.text(),
            content=self.content_edit.toPlainText(),
        )
        self.reload()
