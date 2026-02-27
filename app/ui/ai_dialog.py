import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QFormLayout, QMessageBox, QStackedWidget,
    QInputDialog, QDialog, QDialogButtonBox,
)
from PySide6.QtCore import Qt, QThread, Signal as QSignal


class AIWorker(QThread):
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


class BlockingAIWorker(QThread):
    result_ready = QSignal(str)
    error_signal = QSignal(str)

    def __init__(self, func, args=None, kwargs=None):
        super().__init__()
        self._func = func
        self._args = args or ()
        self._kwargs = kwargs or {}

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))


class AIDialog(QWidget):
    insert_requested = QSignal(str)

    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.ai_tasks = None
        self._worker = None
        self._accumulated = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_output_page())
        self.stack.addWidget(self._build_settings_page())
        layout.addWidget(self.stack)

    def _build_output_page(self):
        page = QWidget()
        vbox = QVBoxLayout(page)

        label = QLabel("AI 助手")
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        vbox.addWidget(label)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("AI 输出将显示在这里...")
        vbox.addWidget(self.output)

        # 快捷操作按钮
        quick_row = QHBoxLayout()
        self.btn_outline = QPushButton("生成大纲")
        self.btn_outline.clicked.connect(self._generate_outline)
        quick_row.addWidget(self.btn_outline)

        self.btn_write_ch1 = QPushButton("写下一章")
        self.btn_write_ch1.clicked.connect(self._write_next_chapter)
        quick_row.addWidget(self.btn_write_ch1)
        vbox.addLayout(quick_row)

        # 控制按钮
        btn_row = QHBoxLayout()
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self._stop_ai)
        self.btn_stop.setEnabled(False)
        btn_row.addWidget(self.btn_stop)

        self.btn_insert = QPushButton("插入到编辑器")
        self.btn_insert.clicked.connect(self._insert_to_editor)
        btn_row.addWidget(self.btn_insert)

        self.btn_settings = QPushButton("设置")
        self.btn_settings.clicked.connect(self.show_settings)
        btn_row.addWidget(self.btn_settings)
        vbox.addLayout(btn_row)

        return page

    def _build_settings_page(self):
        page = QWidget()
        vbox = QVBoxLayout(page)

        label = QLabel("AI 设置")
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        vbox.addWidget(label)

        form = QFormLayout()
        self.input_key = QLineEdit()
        self.input_key.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self.input_key)

        self.input_url = QLineEdit()
        form.addRow("Base URL:", self.input_url)

        self.input_model = QLineEdit()
        form.addRow("Model:", self.input_model)
        vbox.addLayout(form)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save_settings)
        btn_row.addWidget(btn_save)

        btn_back = QPushButton("返回")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_row.addWidget(btn_back)
        vbox.addLayout(btn_row)

        vbox.addStretch()
        return page

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
        self.ai_tasks = AITasks(client, self.project.db)

    def show_settings(self):
        from app.utils.config import Config
        config = Config()
        self.input_key.setText(config.get("ai.api_key", ""))
        self.input_url.setText(config.get("ai.base_url", "https://api.deepseek.com/v1"))
        self.input_model.setText(config.get("ai.model", "deepseek-chat"))
        self.stack.setCurrentIndex(1)

    def _save_settings(self):
        from app.utils.config import Config
        config = Config()
        config.set("ai.api_key", self.input_key.text().strip())
        config.set("ai.base_url", self.input_url.text().strip())
        config.set("ai.model", self.input_model.text().strip())
        config.save()
        self._init_ai_tasks()
        self.stack.setCurrentIndex(0)
        QMessageBox.information(self, "提示", "AI 设置已保存")

    def start_task(self, task_type, content="", chapter_id=None):
        if not self.project:
            QMessageBox.information(self, "提示", "请先新建或打开项目")
            return
        if not self.ai_tasks:
            self._init_ai_tasks()
        if not self.ai_tasks or not self.ai_tasks.client.is_configured:
            QMessageBox.warning(self, "提示", "请先配置 AI（点击设置按钮）")
            self.show_settings()
            return

        self.output.clear()
        self._accumulated = ""

        if task_type == "continue":
            # 主线程构建消息，子线程只做 AI 调用
            msgs = self.ai_tasks.build_continue_messages(content, chapter_id)
            gen = self.ai_tasks.continue_writing_stream(msgs)
            self._run_stream(gen)
        elif task_type == "polish":
            gen = self.ai_tasks.polish(content)
            self._run_stream(gen)
        elif task_type == "summary":
            ch = self.project.db.get_chapter(chapter_id)
            title = ch["title"] if ch else "未知"
            self._summary_chapter_id = chapter_id
            self.output.setPlainText("正在生成摘要...")
            worker = BlockingAIWorker(
                self.ai_tasks.generate_summary_call, args=(content, title)
            )
            worker.result_ready.connect(self._on_summary_done)
            worker.error_signal.connect(self._on_error)
            self._worker = worker
            self.btn_stop.setEnabled(True)
            worker.start()

    def _run_stream(self, gen):
        self._worker = AIWorker(gen)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.error_signal.connect(self._on_error)
        self.btn_stop.setEnabled(True)
        self._worker.start()

    def _on_chunk(self, text):
        self._accumulated += text
        self.output.setPlainText(self._accumulated)
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_finished(self):
        self.btn_stop.setEnabled(False)
        # 如果是写章节任务，自动保存内容到数据库
        if hasattr(self, '_writing_chapter_id') and self._writing_chapter_id and self._accumulated.strip():
            self.project.db.update_chapter(
                self._writing_chapter_id,
                content=self._accumulated.strip(),
                word_count=len(self._accumulated.replace(" ", "").replace("\n", "")),
            )
            title = self.project.db.get_chapter(self._writing_chapter_id)
            ch_title = title["title"] if title else ""
            self.output.append(f"\n\n--- 已自动保存到「{ch_title}」---")
            self._writing_chapter_id = None
            self._refresh_chapter_tree()

    def _on_error(self, msg):
        self.btn_stop.setEnabled(False)
        self.output.append(f"\n\n[错误] {msg}")

    def _on_summary_done(self, result_text):
        self.btn_stop.setEnabled(False)
        # 在主线程中保存到数据库
        data = self.ai_tasks.save_summary_result(result_text, self._summary_chapter_id)
        text = f"摘要: {data.get('summary', '')}\n"
        text += f"关键事件: {', '.join(data.get('key_events', []))}\n"
        changes = data.get('character_changes', {})
        if changes:
            text += "角色变化:\n"
            for name, change in changes.items():
                text += f"  {name}: {change}\n"
        self.output.setPlainText(text)

    def _stop_ai(self):
        if self._worker:
            if hasattr(self._worker, 'stop'):
                self._worker.stop()
            self._worker.quit()
            self.btn_stop.setEnabled(False)

    def _insert_to_editor(self):
        text = self.output.toPlainText().strip()
        if text:
            self.insert_requested.emit(text)

    # ── 生成大纲 ──
    def _generate_outline(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先新建或打开项目")
            return
        if not self.ai_tasks:
            self._init_ai_tasks()
        if not self.ai_tasks or not self.ai_tasks.client.is_configured:
            QMessageBox.warning(self, "提示", "请先配置 AI")
            self.show_settings()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("生成大纲")
        dlg.setMinimumWidth(360)
        form = QFormLayout(dlg)

        title_input = QLineEdit()
        title_input.setPlaceholderText("例：星辰大海")
        form.addRow("小说标题:", title_input)

        genre_input = QLineEdit()
        genre_input.setPlaceholderText("例：玄幻/都市/科幻")
        form.addRow("类型题材:", genre_input)

        idea_input = QTextEdit()
        idea_input.setPlaceholderText("简要描述你的故事构思...")
        idea_input.setMaximumHeight(100)
        form.addRow("故事构思:", idea_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        title = title_input.text().strip()
        genre = genre_input.text().strip()
        idea = idea_input.toPlainText().strip()
        if not title or not idea:
            QMessageBox.warning(self, "提示", "请填写标题和构思")
            return

        self.output.clear()
        self.output.setPlainText("正在生成大纲，请稍候...")
        self.btn_outline.setEnabled(False)
        self.btn_write_ch1.setEnabled(False)

        # 在主线程中预先读取数据库数据
        extra = self.ai_tasks.build_outline_context()

        worker = BlockingAIWorker(
            self.ai_tasks.generate_full_outline, args=(title, genre, idea, extra)
        )
        worker.result_ready.connect(lambda text: self._on_outline_ready(text, title))
        worker.error_signal.connect(self._on_error)
        worker.error_signal.connect(lambda: self.btn_outline.setEnabled(True))
        worker.error_signal.connect(lambda: self.btn_write_ch1.setEnabled(True))
        self._worker = worker
        self.btn_stop.setEnabled(True)
        worker.start()

    def _on_outline_ready(self, text, novel_title):
        self.btn_stop.setEnabled(False)
        self.btn_outline.setEnabled(True)
        self.btn_write_ch1.setEnabled(True)
        self.output.setPlainText(text)

        # 解析大纲并写入数据库
        self._parse_outline_to_chapters(text, novel_title)

    def _parse_outline_to_chapters(self, text, novel_title):
        """解析 AI 生成的大纲，创建卷和章节到数据库"""
        db = self.project.db
        lines = text.split('\n')
        current_volume_id = None
        current_outline_vol_id = None
        chapter_count = 0
        # 先解析出结构：标题行 + 后续概要文本
        entries = []  # [(type, title, summary_lines)]
        for line in lines:
            s = line.strip()
            vol_m = re.match(r'^##\s+(.+)', s)
            ch_m = re.match(r'^###\s+(.+)', s)
            if vol_m:
                entries.append(("vol", vol_m.group(1).strip(), []))
            elif ch_m:
                entries.append(("ch", ch_m.group(1).strip(), []))
            elif entries and s:
                entries[-1][2].append(s)

        for etype, title, summary_lines in entries:
            summary = "\n".join(summary_lines).strip()
            if etype == "vol":
                current_volume_id = db.add_chapter(title=title, parent_id=None)
                current_outline_vol_id = db.add_outline(
                    title=title, level="volume", parent_id=None, content=summary
                )
            elif etype == "ch" and current_volume_id is not None:
                chapter_count += 1
                db.add_chapter(title=title, parent_id=current_volume_id)
                db.add_outline(
                    title=title, level="chapter",
                    parent_id=current_outline_vol_id, content=summary
                )

        if chapter_count > 0:
            QMessageBox.information(
                self, "完成",
                f"大纲已生成并导入！共创建 {chapter_count} 个章节。\n"
                "请在左侧章节树和大纲面板中查看。"
            )
            self._refresh_chapter_tree()
        else:
            QMessageBox.warning(self, "提示", "未能从大纲中解析出章节，请检查 AI 输出格式。")

    def _refresh_chapter_tree(self):
        """向上查找主窗口并刷新章节树和大纲面板"""
        widget = self.parent()
        while widget:
            if hasattr(widget, 'chapter_tree'):
                widget.chapter_tree.reload()
                if hasattr(widget, 'outline_panel'):
                    widget.outline_panel.reload()
                return
            widget = widget.parent() if hasattr(widget, 'parent') else None

    # ── 写下一章 ──
    def _write_next_chapter(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先新建或打开项目")
            return
        if not self.ai_tasks:
            self._init_ai_tasks()
        if not self.ai_tasks or not self.ai_tasks.client.is_configured:
            QMessageBox.warning(self, "提示", "请先配置 AI")
            self.show_settings()
            return

        db = self.project.db
        # 按顺序遍历所有卷→章，找到第一个没有内容的章节
        volumes = db.get_chapters(parent_id=None)
        if not volumes:
            QMessageBox.warning(self, "提示", "请先生成大纲（需要有卷和章节）")
            return

        target_chapter = None
        for vol in volumes:
            children = db.get_chapters(parent_id=vol["id"])
            for ch in children:
                content = (ch["content"] or "").strip()
                # 去掉 HTML 标签后判断是否为空
                import re as _re
                plain = _re.sub(r'<[^>]+>', '', content).strip()
                if not plain:
                    target_chapter = ch
                    break
            if target_chapter:
                break

        if not target_chapter:
            QMessageBox.information(self, "提示", "所有章节都已有内容，没有需要写的章节了。")
            return

        title = target_chapter["title"]
        # 获取大纲内容
        outlines = db.get_outlines(parent_id=None)
        outline_text = ""
        for o in outlines:
            outline_text += f"{o['title']}\n{o['content']}\n"

        self.output.clear()
        self._accumulated = ""
        self.output.setPlainText(f"正在撰写「{title}」...")

        # 主线程构建消息，子线程只做 AI 调用
        msgs = self.ai_tasks.build_write_chapter_messages(title, outline_text, target_chapter["id"])
        gen = self.ai_tasks.write_chapter_stream(msgs)
        self._writing_chapter_id = target_chapter["id"]
        self._run_stream(gen)
