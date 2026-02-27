from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QLineEdit, QFormLayout, QGroupBox,
    QMessageBox, QStackedWidget,
)
from PySide6.QtCore import Qt, QThread, Signal as QSignal


class AIWorker(QThread):
    """后台线程执行 AI 流式请求"""
    chunk_received = QSignal(str)
    finished_signal = QSignal()
    error_signal = QSignal(str)

    def __init__(self, stream_gen):
        super().__init__()
        self._gen = stream_gen
        self._stopped = False

    def run(self):
        try:
            for chunk in self._gen:
                if self._stopped:
                    break
                self.chunk_received.emit(chunk)
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()

    def stop(self):
        self._stopped = True


class AIDialog(QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self._ai_tasks = None
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("AI 助手")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.stack = QStackedWidget()

        # 页面0：AI 输出面板
        self.output_page = QWidget()
        out_layout = QVBoxLayout(self.output_page)
        out_layout.setContentsMargins(0, 0, 0, 0)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("AI 输出将显示在这里...")
        out_layout.addWidget(self.output_text)

        btn_layout = QHBoxLayout()
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_ai)
        self.btn_insert = QPushButton("插入到编辑器")
        self.btn_insert.clicked.connect(self._insert_to_editor)
        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_insert)
        btn_layout.addWidget(self.btn_settings)
        out_layout.addLayout(btn_layout)
        self.stack.addWidget(self.output_page)

        # 页面1：设置面板
        self.settings_page = QWidget()
        settings_layout = QFormLayout(self.settings_page)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        settings_layout.addRow("API Key:", self.api_key_edit)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        settings_layout.addRow("Base URL:", self.base_url_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("gpt-4o")
        settings_layout.addRow("模型:", self.model_edit)

        btn_save_settings = QPushButton("保存设置")
        btn_save_settings.clicked.connect(self._save_settings)
        settings_layout.addRow(btn_save_settings)

        btn_back = QPushButton("返回")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        settings_layout.addRow(btn_back)

        self.stack.addWidget(self.settings_page)
        layout.addWidget(self.stack)

    def set_project(self, project):
        self.project = project
        self._init_ai_tasks()

    def _init_ai_tasks(self):
        if not self.project:
            return
        from app.ai.client import AIClient
        from app.ai.tasks import AITasks
        from app.utils.config import Config
        config = Config()
        client = AIClient(config)
        self._ai_tasks = AITasks(client, self.project.db)
        # 加载设置到 UI
        self.api_key_edit.setText(config.get("ai.api_key", ""))
        self.base_url_edit.setText(config.get("ai.base_url", "https://api.openai.com/v1"))
        self.model_edit.setText(config.get("ai.model", "gpt-4o"))

    def show_settings(self):
        self.stack.setCurrentIndex(1)

    def _save_settings(self):
        from app.utils.config import Config
        config = Config()
        config.set("ai.api_key", self.api_key_edit.text())
        config.set("ai.base_url", self.base_url_edit.text() or "https://api.openai.com/v1")
        config.set("ai.model", self.model_edit.text() or "gpt-4o")
        self._init_ai_tasks()
        QMessageBox.information(self, "提示", "AI 设置已保存")
        self.stack.setCurrentIndex(0)

    def start_task(self, task_type: str, content: str, **kwargs):
        """启动 AI 任务"""
        if not self._ai_tasks:
            QMessageBox.warning(self, "提示", "请先配置 AI 设置")
            self.show_settings()
            return
        if not self._ai_tasks.client.is_configured:
            QMessageBox.warning(self, "提示", "请先设置 API Key")
            self.show_settings()
            return

        self.stack.setCurrentIndex(0)
        self.output_text.clear()
        self.btn_stop.setEnabled(True)
        self._task_type = task_type

        try:
            if task_type == "continue":
                chapter_id = kwargs.get("chapter_id")
                gen = self._ai_tasks.continue_writing(content, chapter_id)
                self._run_stream(gen)
            elif task_type == "polish":
                gen = self._ai_tasks.polish(content)
                self._run_stream(gen)
            elif task_type == "summary":
                chapter_id = kwargs.get("chapter_id")
                if chapter_id:
                    ch = self.project.db.get_chapter(chapter_id)
                    title = ch["title"] if ch else ""
                    result = self._ai_tasks.generate_summary(content, title, chapter_id)
                    self.output_text.setPlainText(
                        f"摘要: {result.get('summary', '')}\n\n"
                        f"关键事件: {', '.join(result.get('key_events', []))}\n\n"
                        f"角色变化: {result.get('character_changes', {})}"
                    )
                    self.btn_stop.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "AI 错误", str(e))
            self.btn_stop.setEnabled(False)

    def _run_stream(self, gen):
        """启动流式输出线程"""
        self._worker = AIWorker(gen)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, text):
        self.output_text.moveCursor(self.output_text.textCursor().End)
        self.output_text.insertPlainText(text)

    def _on_finished(self):
        self.btn_stop.setEnabled(False)
        self._worker = None

    def _on_error(self, msg):
        self.output_text.append(f"\n\n[错误] {msg}")
        self.btn_stop.setEnabled(False)

    def _stop_ai(self):
        if self._worker:
            self._worker.stop()
            self.btn_stop.setEnabled(False)

    def _insert_to_editor(self):
        text = self.output_text.toPlainText()
        if not text:
            return
        main_win = self.window()
        if hasattr(main_win, "editor"):
            main_win.editor.append_text(text)
