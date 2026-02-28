from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QStackedWidget, QToolBar,
    QStatusBar, QMessageBox, QFileDialog, QLabel, QApplication,
)
from PySide6.QtCore import Qt, QTimer, QUrl, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence, QDesktopServices

from app.ui.chapter_tree import ChapterTree
from app.ui.editor import Editor
from app.ui.character_panel import CharacterPanel
from app.ui.outline_panel import OutlinePanel
from app.ui.world_panel import WorldPanel
from app.ui.ai_dialog import AIDialog


class _UpdateChecker(QThread):
    result_ready = Signal(str, str)  # (latest_version, error)

    def run(self):
        import urllib.request, json
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/dysobo/novel-editor/releases/latest",
                headers={"User-Agent": "novel-editor"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                tag = json.loads(resp.read().decode())["tag_name"].lstrip("v")
            self.result_ready.emit(tag, "")
        except Exception:
            self.result_ready.emit("", "timeout")


class MainWindow(QMainWindow):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.setWindowTitle("小说编辑器")
        self.setMinimumSize(1200, 700)
        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_statusbar()
        self._init_auto_save()

    def _init_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：章节树
        self.chapter_tree = ChapterTree(self.project)
        splitter.addWidget(self.chapter_tree)

        # 中间：编辑器
        self.editor = Editor()
        splitter.addWidget(self.editor)

        # 右侧：面板栈
        self.right_stack = QStackedWidget()
        self.character_panel = CharacterPanel(self.project)
        self.outline_panel = OutlinePanel(self.project)
        self.world_panel = WorldPanel(self.project)
        self.ai_dialog = AIDialog(self.project)

        self.right_stack.addWidget(self.character_panel)
        self.right_stack.addWidget(self.outline_panel)
        self.right_stack.addWidget(self.world_panel)
        self.right_stack.addWidget(self.ai_dialog)
        splitter.addWidget(self.right_stack)

        splitter.setSizes([220, 600, 320])
        self.setCentralWidget(splitter)

        # 信号连接
        self.chapter_tree.chapter_selected.connect(self._on_chapter_selected)
        self.editor.content_changed.connect(self._on_content_changed)
        self.ai_dialog.insert_requested.connect(self._on_ai_insert)
        self.outline_panel.chapter_locate_requested.connect(self.chapter_tree.locate_chapter)

    def _init_menu(self):
        mb = self.menuBar()

        # 文件菜单
        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction(self._action("新建项目", "Ctrl+N", self._new_project))
        file_menu.addAction(self._action("打开项目", "Ctrl+O", self._open_project))
        file_menu.addAction(self._action("保存", "Ctrl+S", self._save_current))
        file_menu.addSeparator()
        file_menu.addAction(self._action("导出 TXT", "", self._export_txt))
        file_menu.addAction(self._action("导出 DOCX", "", self._export_docx))

        # 视图菜单
        view_menu = mb.addMenu("视图(&V)")
        view_menu.addAction(self._action("角色管理", "Ctrl+1", lambda: self.right_stack.setCurrentIndex(0)))
        view_menu.addAction(self._action("大纲", "Ctrl+2", lambda: self.right_stack.setCurrentIndex(1)))
        view_menu.addAction(self._action("世界观", "Ctrl+3", lambda: self.right_stack.setCurrentIndex(2)))
        view_menu.addAction(self._action("AI 助手", "Ctrl+4", lambda: self.right_stack.setCurrentIndex(3)))

        # AI 菜单
        ai_menu = mb.addMenu("AI(&A)")
        ai_menu.addAction(self._action("AI 续写", "Ctrl+J", self._ai_continue))
        ai_menu.addAction(self._action("AI 润色", "Ctrl+L", self._ai_polish))
        ai_menu.addAction(self._action("生成摘要", "", self._ai_summary))
        ai_menu.addSeparator()
        ai_menu.addAction(self._action("AI 设置", "", self._ai_settings))

        # 关于菜单
        help_menu = mb.addMenu("关于(&H)")
        help_menu.addAction(self._action("使用说明", "", self._show_usage_guide))
        help_menu.addAction(self._action("项目主页", "", self._open_homepage))
        help_menu.addAction(self._action("检查更新", "", self._check_update))

        # 右上角版本号
        version = QApplication.instance().applicationVersion()
        ver_label = QLabel(f"v{version}  ")
        ver_label.setStyleSheet("color: gray; padding-right: 8px;")
        mb.setCornerWidget(ver_label, Qt.TopRightCorner)

    def _action(self, text, shortcut, callback):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(callback)
        return act

    def _init_toolbar(self):
        tb = QToolBar("面板切换")
        tb.setMovable(False)
        tb.addAction(self._action("角色", "", lambda: self.right_stack.setCurrentIndex(0)))
        tb.addAction(self._action("大纲", "", lambda: self.right_stack.setCurrentIndex(1)))
        tb.addAction(self._action("世界观", "", lambda: self.right_stack.setCurrentIndex(2)))
        tb.addAction(self._action("AI", "", lambda: self.right_stack.setCurrentIndex(3)))
        self.addToolBar(Qt.RightToolBarArea, tb)

    def _init_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.word_count_label = QLabel("字数: 0")
        self.status_bar.addPermanentWidget(self.word_count_label)

    def _init_auto_save(self):
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._save_current)
        self._auto_save_timer.start(30000)

    # ── 槽函数 ──
    def _on_chapter_selected(self, chapter_id):
        self._save_current()
        self._current_chapter_id = chapter_id
        self.ai_dialog.set_chat_chapter_id(chapter_id)
        if self.project:
            ch = self.project.db.get_chapter(chapter_id)
            if ch:
                self.editor.set_content(ch["content"] or "")
                self.word_count_label.setText(f"字数: {ch['word_count']}")

    def _on_content_changed(self):
        text = self.editor.get_plain_text()
        wc = len(text.replace(" ", "").replace("\n", ""))
        self.word_count_label.setText(f"字数: {wc}")

    def _save_current(self):
        if not self.project or not hasattr(self, "_current_chapter_id"):
            return
        content = self.editor.get_content()
        plain = self.editor.get_plain_text()
        wc = len(plain.replace(" ", "").replace("\n", ""))
        self.project.db.update_chapter(
            self._current_chapter_id, content=content, word_count=wc
        )

    def _new_project(self):
        from app.core.project import Project
        path, _ = QFileDialog.getSaveFileName(
            self, "新建项目", "", "小说项目 (*.novel)"
        )
        if path:
            if not path.endswith(".novel"):
                path += ".novel"
            self.project = Project.create(path)
            self._reload_project()

    def _open_project(self):
        from app.core.project import Project
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "小说项目 (*.novel)"
        )
        if path:
            self.project = Project.open(path)
            self._reload_project()

    def _reload_project(self):
        self.setWindowTitle(f"小说编辑器 - {self.project.name}")
        self.chapter_tree.set_project(self.project)
        self.character_panel.set_project(self.project)
        self.outline_panel.set_project(self.project)
        self.world_panel.set_project(self.project)
        self.ai_dialog.set_project(self.project)
        self.editor.clear()

    def _export_txt(self):
        if not self.project:
            return
        from app.core.export import export_txt
        path, _ = QFileDialog.getSaveFileName(self, "导出 TXT", "", "文本文件 (*.txt)")
        if path:
            export_txt(self.project.db, path)
            self.status_bar.showMessage("已导出 TXT", 3000)

    def _export_docx(self):
        if not self.project:
            return
        from app.core.export import export_docx
        path, _ = QFileDialog.getSaveFileName(self, "导出 DOCX", "", "Word 文档 (*.docx)")
        if path:
            export_docx(self.project.db, path)
            self.status_bar.showMessage("已导出 DOCX", 3000)

    def _ai_continue(self):
        self.right_stack.setCurrentIndex(3)
        self.ai_dialog.start_task("continue", self.editor.get_plain_text())

    def _ai_polish(self):
        selected = self.editor.get_selected_text()
        if not selected:
            QMessageBox.information(self, "提示", "请先选中要润色的文本")
            return
        self.right_stack.setCurrentIndex(3)
        self.ai_dialog.start_task("polish", selected)

    def _ai_summary(self):
        if not self.project or not hasattr(self, "_current_chapter_id"):
            return
        self.right_stack.setCurrentIndex(3)
        self.ai_dialog.start_task("summary", self.editor.get_plain_text(),
                                   chapter_id=self._current_chapter_id)

    def _on_ai_insert(self, text):
        self.editor.insert_text(text)

    def _ai_settings(self):
        self.right_stack.setCurrentIndex(3)
        self.ai_dialog.show_settings()

    def _show_usage_guide(self):
        QMessageBox.information(self, "使用说明",
            "1. 在 AI 设置中配置 API 密钥\n"
            "2. 新建或打开项目\n"
            "3. 编写角色设定和世界观\n"
            "4. 生成或编写大纲\n"
            "5. 逐章撰写，可使用 AI 续写/润色辅助")

    def _open_homepage(self):
        QDesktopServices.openUrl(QUrl("https://github.com/dysobo/novel-editor"))

    def _check_update(self):
        self.status_bar.showMessage("正在检查更新…")
        self._update_checker = _UpdateChecker()
        self._update_checker.result_ready.connect(self._on_update_result)
        self._update_checker.start()

    def _on_update_result(self, latest, error):
        self.status_bar.clearMessage()
        current = QApplication.instance().applicationVersion()
        if error:
            QMessageBox.information(self, "检查更新", "无法连接到服务器，请检查网络后重试")
        elif latest == current:
            QMessageBox.information(self, "检查更新", f"当前已是最新版本 v{current}")
        else:
            QMessageBox.information(self, "检查更新",
                f"发现新版本 v{latest}（当前 v{current}）\n请前往项目主页下载更新")

    def set_project(self, project):
        self.project = project
        self._reload_project()

    def closeEvent(self, event):
        self._save_current()
        if self.project:
            self.project.db.close()
        event.accept()
