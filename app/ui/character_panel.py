from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QTextEdit, QLineEdit, QInputDialog,
    QMessageBox, QFormLayout, QGroupBox, QSplitter,
)
from PySide6.QtCore import Qt


class CharacterPanel(QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self._current_id = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("角色管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Vertical)

        # 上半：角色列表
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("+ 添加角色")
        btn_del = QPushButton("删除")
        btn_add.clicked.connect(self._add_character)
        btn_del.clicked.connect(self._delete_character)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        top_layout.addLayout(btn_layout)

        self.char_list = QListWidget()
        self.char_list.currentItemChanged.connect(self._on_select)
        top_layout.addWidget(self.char_list)
        splitter.addWidget(top)

        # 下半：角色详情
        bottom = QWidget()
        form_layout = QFormLayout(bottom)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("角色名称")
        form_layout.addRow("名称:", self.name_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("角色描述、性格、外貌、背景...")
        self.desc_edit.setMaximumHeight(200)
        form_layout.addRow("描述:", self.desc_edit)

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save_character)
        form_layout.addRow(btn_save)
        splitter.addWidget(bottom)

        layout.addWidget(splitter)

    def set_project(self, project):
        self.project = project
        self.reload()

    def reload(self):
        self.char_list.clear()
        self._current_id = None
        self.name_edit.clear()
        self.desc_edit.clear()
        if not self.project:
            return
        for ch in self.project.db.get_characters():
            item = QListWidgetItem(ch["name"])
            item.setData(Qt.UserRole, ch["id"])
            self.char_list.addItem(item)

    def _on_select(self, current, previous):
        if not current or not self.project:
            return
        cid = current.data(Qt.UserRole)
        self._current_id = cid
        ch = self.project.db.get_character(cid)
        if ch:
            self.name_edit.setText(ch["name"])
            self.desc_edit.setPlainText(ch["description"] or "")

    def _add_character(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先通过 文件→新建项目 或 文件→打开项目 创建/打开一个项目")
            return
        name, ok = QInputDialog.getText(self, "新建角色", "角色名称:")
        if ok and name:
            self.project.db.add_character(name)
            self.reload()

    def _delete_character(self):
        if not self.project or self._current_id is None:
            return
        ret = QMessageBox.question(self, "确认", "确定删除该角色？")
        if ret == QMessageBox.Yes:
            self.project.db.delete_character(self._current_id)
            self.reload()

    def _save_character(self):
        if not self.project or self._current_id is None:
            return
        self.project.db.update_character(
            self._current_id,
            name=self.name_edit.text(),
            description=self.desc_edit.toPlainText(),
        )
        # 刷新列表中的名称
        current = self.char_list.currentItem()
        if current:
            current.setText(self.name_edit.text())
