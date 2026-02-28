from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QTextEdit, QLineEdit, QInputDialog,
    QMessageBox, QFormLayout, QSplitter, QTabWidget, QComboBox,
    QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt
from app.ui.relationship_graph import RelationshipGraph, RELATION_COLORS


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

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_list_tab(), "角色列表")
        self.tabs.addTab(self._build_graph_tab(), "关系图")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _build_list_tab(self):
        tab = QWidget()
        splitter = QSplitter(Qt.Vertical)
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

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

        tab_layout.addWidget(splitter)
        return tab

    def _build_graph_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(0, 0, 0, 0)

        # 关系图
        self.graph = RelationshipGraph()
        vbox.addWidget(self.graph)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_add_rel = QPushButton("+ 添加关系")
        btn_add_rel.clicked.connect(self._add_relationship)
        btn_row.addWidget(btn_add_rel)

        btn_del_rel = QPushButton("删除关系")
        btn_del_rel.clicked.connect(self._delete_relationship)
        btn_row.addWidget(btn_del_rel)
        vbox.addLayout(btn_row)

        # 关系列表
        self.rel_list = QListWidget()
        self.rel_list.setMaximumHeight(120)
        vbox.addWidget(self.rel_list)

        return tab

    def _on_tab_changed(self, index):
        if index == 1:
            self._refresh_graph()

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
        if self.tabs.currentIndex() == 1:
            self._refresh_graph()

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
            QMessageBox.information(self, "提示", "请先创建或打开项目")
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
        current = self.char_list.currentItem()
        if current:
            current.setText(self.name_edit.text())

    # ── 关系图相关 ──
    def _refresh_graph(self):
        if not self.project:
            return
        characters = [dict(c) for c in self.project.db.get_characters()]
        relationships = [dict(r) for r in self.project.db.get_relationships()]
        self.graph.set_data(characters, relationships)
        # 刷新关系列表
        self.rel_list.clear()
        for r in relationships:
            text = f"{r['name_a']} ↔ {r['name_b']}：{r['relation_type']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, r["id"])
            self.rel_list.addItem(item)

    def _add_relationship(self):
        if not self.project:
            return
        characters = self.project.db.get_characters()
        if len(characters) < 2:
            QMessageBox.warning(self, "提示", "至少需要2个角色才能添加关系")
            return

        names = [c["name"] for c in characters]
        ids = [c["id"] for c in characters]

        dlg = QDialog(self)
        dlg.setWindowTitle("添加角色关系")
        dlg.setMinimumWidth(300)
        form = QFormLayout(dlg)

        combo_a = QComboBox()
        combo_a.addItems(names)
        form.addRow("角色A:", combo_a)

        combo_b = QComboBox()
        combo_b.addItems(names)
        if len(names) > 1:
            combo_b.setCurrentIndex(1)
        form.addRow("角色B:", combo_b)

        rel_types = list(RELATION_COLORS.keys())
        combo_type = QComboBox()
        combo_type.addItems(rel_types)
        form.addRow("关系类型:", combo_type)

        desc_input = QLineEdit()
        desc_input.setPlaceholderText("关系描述（可选）")
        form.addRow("描述:", desc_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        idx_a = combo_a.currentIndex()
        idx_b = combo_b.currentIndex()
        if idx_a == idx_b:
            QMessageBox.warning(self, "提示", "不能选择同一个角色")
            return

        self.project.db.add_relationship(
            ids[idx_a], ids[idx_b],
            combo_type.currentText(),
            desc_input.text().strip(),
        )
        self._refresh_graph()

    def _delete_relationship(self):
        if not self.project:
            return
        current = self.rel_list.currentItem()
        if not current:
            QMessageBox.information(self, "提示", "请先在关系列表中选择一条关系")
            return
        rel_id = current.data(Qt.UserRole)
        ret = QMessageBox.question(self, "确认", "确定删除该关系？")
        if ret == QMessageBox.Yes:
            self.project.db.delete_relationship(rel_id)
            self._refresh_graph()
