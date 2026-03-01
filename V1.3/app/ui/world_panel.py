from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QTextEdit, QLineEdit, QInputDialog,
    QMessageBox, QComboBox, QSplitter, QFormLayout,
)
from PySide6.QtCore import Qt


class WorldPanel(QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self._current_id = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("世界观设定")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # 分类筛选
        filter_layout = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部")
        self.category_combo.currentTextChanged.connect(self._on_filter)
        filter_layout.addWidget(QLabel("分类:"))
        filter_layout.addWidget(self.category_combo)
        layout.addLayout(filter_layout)

        splitter = QSplitter(Qt.Vertical)

        # 上半：设定列表
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("+ 添加设定")
        btn_del = QPushButton("删除")
        btn_add.clicked.connect(self._add_setting)
        btn_del.clicked.connect(self._delete_setting)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        top_layout.addLayout(btn_layout)

        self.setting_list = QTreeWidget()
        self.setting_list.setHeaderLabels(["标题", "分类"])
        self.setting_list.currentItemChanged.connect(self._on_select)
        top_layout.addWidget(self.setting_list)
        splitter.addWidget(top)

        # 下半：编辑区
        bottom = QWidget()
        form = QFormLayout(bottom)
        self.title_edit = QLineEdit()
        form.addRow("标题:", self.title_edit)
        self.cat_edit = QLineEdit()
        self.cat_edit.setPlaceholderText("如：地理、魔法体系、势力...")
        form.addRow("分类:", self.cat_edit)
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("详细设定内容...")
        form.addRow("内容:", self.content_edit)
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save_setting)
        form.addRow(btn_save)
        splitter.addWidget(bottom)

        layout.addWidget(splitter)

    def set_project(self, project):
        self.project = project
        self.reload()

    def reload(self):
        self.setting_list.clear()
        self._current_id = None
        self.title_edit.clear()
        self.cat_edit.clear()
        self.content_edit.clear()
        if not self.project:
            return
        # 刷新分类下拉
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("全部")
        for cat in self.project.db.get_world_categories():
            self.category_combo.addItem(cat)
        self.category_combo.blockSignals(False)
        self._load_settings()

    def _load_settings(self, category=None):
        self.setting_list.clear()
        if not self.project:
            return
        settings = self.project.db.get_world_settings(category)
        for s in settings:
            item = QTreeWidgetItem([s["title"], s["category"]])
            item.setData(0, Qt.UserRole, s["id"])
            self.setting_list.addTopLevelItem(item)

    def _on_filter(self, text):
        cat = None if text == "全部" else text
        self._load_settings(cat)

    def _on_select(self, current, previous):
        if not current or not self.project:
            return
        sid = current.data(0, Qt.UserRole)
        self._current_id = sid
        settings = self.project.db.get_world_settings()
        for s in settings:
            if s["id"] == sid:
                self.title_edit.setText(s["title"])
                self.cat_edit.setText(s["category"])
                self.content_edit.setPlainText(s["content"] or "")
                break

    def _add_setting(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先通过 文件→新建项目 或 文件→打开项目 创建/打开一个项目")
            return
        title, ok = QInputDialog.getText(self, "新建设定", "设定标题:")
        if ok and title:
            cat, ok2 = QInputDialog.getText(self, "分类", "分类名称:", text="通用")
            if ok2:
                self.project.db.add_world_setting(title, category=cat or "通用")
                self.reload()

    def _delete_setting(self):
        if not self.project or self._current_id is None:
            return
        ret = QMessageBox.question(self, "确认", "确定删除该设定？")
        if ret == QMessageBox.Yes:
            self.project.db.delete_world_setting(self._current_id)
            self.reload()

    def _save_setting(self):
        if not self.project or self._current_id is None:
            return
        self.project.db.update_world_setting(
            self._current_id,
            title=self.title_edit.text(),
            category=self.cat_edit.text() or "通用",
            content=self.content_edit.toPlainText(),
        )
        self.reload()
