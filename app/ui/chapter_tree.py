from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog, QMessageBox, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QAction


class ChapterTree(QWidget):
    chapter_selected = Signal(int)

    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 顶部按钮
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("+ 章节")
        btn_add_vol = QPushButton("+ 卷")
        btn_add.clicked.connect(self._add_chapter)
        btn_add_vol.clicked.connect(self._add_volume)
        btn_layout.addWidget(btn_add_vol)
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)

        # 树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("章节目录")
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.currentItemChanged.connect(self._on_item_changed)
        self.tree.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self.tree)

    def set_project(self, project):
        self.project = project
        self.reload()

    def reload(self):
        self.tree.clear()
        if not self.project:
            return
        self._load_children(0, self.tree.invisibleRootItem())
        self.tree.expandAll()

    def _load_children(self, parent_id, parent_item):
        chapters = self.project.db.get_chapters(parent_id)
        for ch in chapters:
            item = QTreeWidgetItem([ch["title"]])
            item.setData(0, Qt.UserRole, ch["id"])
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            parent_item.addChild(item)
            self._load_children(ch["id"], item)

    def _on_item_changed(self, current, previous):
        if current:
            chapter_id = current.data(0, Qt.UserRole)
            if chapter_id:
                self.chapter_selected.emit(chapter_id)

    def _on_rows_moved(self):
        self._save_sort_order(self.tree.invisibleRootItem(), 0)

    def _save_sort_order(self, parent_item, parent_id):
        if not self.project:
            return
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            ch_id = child.data(0, Qt.UserRole)
            if ch_id:
                self.project.db.move_chapter(ch_id, parent_id, i)
                self._save_sort_order(child, ch_id)

    def _add_volume(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先通过 文件→新建项目 或 文件→打开项目 创建/打开一个项目")
            return
        name, ok = QInputDialog.getText(self, "新建卷", "卷名:")
        if ok and name:
            max_order = len(self.project.db.get_chapters(0))
            self.project.db.add_chapter(name, parent_id=0, sort_order=max_order)
            self.reload()

    def _add_chapter(self):
        if not self.project:
            return
        parent_id = 0
        current = self.tree.currentItem()
        if current:
            pid = current.data(0, Qt.UserRole)
            if pid:
                parent_id = pid
        name, ok = QInputDialog.getText(self, "新建章节", "章节名:")
        if ok and name:
            max_order = len(self.project.db.get_chapters(parent_id))
            self.project.db.add_chapter(name, parent_id=parent_id, sort_order=max_order)
            self.reload()

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            ch_id = item.data(0, Qt.UserRole)
            menu.addAction("重命名", lambda: self._rename_chapter(item, ch_id))
            menu.addAction("添加子章节", lambda: self._add_sub_chapter(ch_id))
            menu.addSeparator()
            menu.addAction("删除", lambda: self._delete_chapter(ch_id))
        else:
            menu.addAction("新建卷", self._add_volume)
            menu.addAction("新建章节", self._add_chapter)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _rename_chapter(self, item, ch_id):
        name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=item.text(0))
        if ok and name:
            self.project.db.update_chapter(ch_id, title=name)
            item.setText(0, name)

    def _add_sub_chapter(self, parent_id):
        name, ok = QInputDialog.getText(self, "新建子章节", "章节名:")
        if ok and name:
            max_order = len(self.project.db.get_chapters(parent_id))
            self.project.db.add_chapter(name, parent_id=parent_id, sort_order=max_order)
            self.reload()

    def _delete_chapter(self, ch_id):
        ret = QMessageBox.question(self, "确认删除", "确定要删除此章节及其所有子章节吗？")
        if ret == QMessageBox.Yes:
            self.project.db.delete_chapter(ch_id)
            self.reload()
