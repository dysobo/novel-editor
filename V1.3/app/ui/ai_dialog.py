import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QFormLayout, QMessageBox, QStackedWidget,
    QInputDialog, QDialog, QDialogButtonBox, QListWidget,
    QListWidgetItem, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, QTimer, Signal as QSignal


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
        self._batch_mode = False
        self._batch_queue = []
        self._batch_total = 0
        self._batch_done = 0
        self._batch_failed = 0
        self._writing_chapter_id = None
        self._chat_history = []
        self._chat_chapter_id = None
        self._chat_accumulated = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_output_page())
        self.stack.addWidget(self._build_settings_page())
        self.stack.addWidget(self._build_chat_page())
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

        self.btn_write_ch1 = QPushButton("写章节")
        self.btn_write_ch1.clicked.connect(self._write_next_chapter)
        quick_row.addWidget(self.btn_write_ch1)

        self.btn_batch = QPushButton("批量写章节")
        self.btn_batch.clicked.connect(self._batch_write_chapters)
        quick_row.addWidget(self.btn_batch)
        vbox.addLayout(quick_row)

        # 批量进度条
        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        vbox.addWidget(self.batch_progress)
        self.batch_label = QLabel("")
        self.batch_label.setVisible(False)
        vbox.addWidget(self.batch_label)

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

        self.btn_chat_mode = QPushButton("对话模式")
        self.btn_chat_mode.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        btn_row.addWidget(self.btn_chat_mode)
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

    def _build_chat_page(self):
        page = QWidget()
        vbox = QVBoxLayout(page)

        # 顶部标题栏
        top_row = QHBoxLayout()
        label = QLabel("AI 对话")
        label.setStyleSheet("font-size: 14px; font-weight: bold;")
        top_row.addWidget(label)
        top_row.addStretch()
        btn_back = QPushButton("返回")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        top_row.addWidget(btn_back)
        vbox.addLayout(top_row)

        # 消息显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("与 AI 讨论你的小说...")
        vbox.addWidget(self.chat_display)

        # 输入区
        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("输入你的问题...")
        self.chat_input.setMaximumHeight(80)
        vbox.addWidget(self.chat_input)

        # 按钮行
        btn_row = QHBoxLayout()
        self.btn_send = QPushButton("发送")
        self.btn_send.clicked.connect(self._send_chat)
        btn_row.addWidget(self.btn_send)

        self.btn_clear_chat = QPushButton("清空对话")
        self.btn_clear_chat.clicked.connect(self._clear_chat)
        btn_row.addWidget(self.btn_clear_chat)
        vbox.addLayout(btn_row)

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

        if self._writing_chapter_id is None:
            return

        chapter_id = self._writing_chapter_id
        self._writing_chapter_id = None
        generated = self._accumulated.strip()

        if generated:
            self.project.db.update_chapter(
                chapter_id,
                content=generated,
                word_count=len(generated.replace(" ", "").replace("\n", "")),
            )
            title = self.project.db.get_chapter(chapter_id)
            ch_title = title["title"] if title else ""
            self.output.append(f"\n\n--- 已自动保存到「{ch_title}」---")
            self._refresh_chapter_tree()

            if self._batch_mode:
                self._advance_batch(success=True)
        else:
            self.output.append("\n\n[提示] 本章未生成有效内容")
            if self._batch_mode:
                self._advance_batch(success=False)
    def _on_error(self, msg):
        self.btn_stop.setEnabled(False)
        self.output.append(f"\n\n[错误] {msg}")

        if self._writing_chapter_id is not None:
            self._writing_chapter_id = None
            if self._batch_mode:
                self._advance_batch(success=False)
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
        # 批量模式下停止整个队列
        if self._batch_mode:
            self._batch_queue.clear()
            self._writing_chapter_id = None
            self._finish_batch(stopped=True)
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
                ch_id = db.add_chapter(title=title, parent_id=current_volume_id)
                db.add_outline(
                    title=title, level="chapter",
                    parent_id=current_outline_vol_id, content=summary,
                    chapter_id=ch_id
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

    # ── 写章节 ──
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
        volumes = db.get_chapters(parent_id=None)
        if not volumes:
            QMessageBox.warning(self, "提示", "请先生成大纲（需要有卷和章节）")
            return

        # 构建章节列表供选择
        chapter_list = []  # [(display_text, chapter_id, has_content)]
        first_empty_idx = -1
        for vol in volumes:
            children = db.get_chapters(parent_id=vol["id"])
            for ch in children:
                plain = re.sub(r'<[^>]+>', '', (ch["content"] or "")).strip()
                has_content = bool(plain)
                mark = "✓" if has_content else "○"
                display = f"{mark}  {vol['title']} / {ch['title']}"
                chapter_list.append((display, ch["id"], has_content))
                if first_empty_idx < 0 and not has_content:
                    first_empty_idx = len(chapter_list) - 1

        if not chapter_list:
            QMessageBox.warning(self, "提示", "未找到章节，请先生成大纲")
            return

        # 弹出选择对话框
        items = [c[0] for c in chapter_list]
        default_idx = first_empty_idx if first_empty_idx >= 0 else 0
        chosen, ok = QInputDialog.getItem(
            self, "选择章节", "选择要生成的章节（✓ 已有内容，○ 待生成）：",
            items, default_idx, False,
        )
        if not ok:
            return

        idx = items.index(chosen)
        chapter_id = chapter_list[idx][1]
        target = db.get_chapter(chapter_id)

        if chapter_list[idx][2]:
            ret = QMessageBox.question(
                self, "确认", f"「{target['title']}」已有内容，重新生成将覆盖。继续？"
            )
            if ret != QMessageBox.Yes:
                return

        self._start_write_chapter(target)

    def _start_write_chapter(self, chapter):
        """根据大纲生成指定章节内容"""
        db = self.project.db
        title = chapter["title"]

        outlines = db.get_outlines(parent_id=None)
        outline_text = ""
        for o in outlines:
            outline_text += f"{o['title']}\n{o['content']}\n"

        self.output.clear()
        self._accumulated = ""
        self.output.setPlainText(f"正在撰写「{title}」...")

        msgs = self.ai_tasks.build_write_chapter_messages(title, outline_text, chapter["id"])
        gen = self.ai_tasks.write_chapter_stream(msgs)
        self._writing_chapter_id = chapter["id"]
        self._run_stream(gen)

    # ── 批量写章节 ──
    def _batch_write_chapters(self):
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
        volumes = db.get_chapters(parent_id=None)
        if not volumes:
            QMessageBox.warning(self, "提示", "请先生成大纲")
            return

        # 构建章节列表
        chapter_list = []
        for vol in volumes:
            for ch in db.get_chapters(parent_id=vol["id"]):
                plain = re.sub(r'<[^>]+>', '', (ch["content"] or "")).strip()
                has_content = bool(plain)
                chapter_list.append((vol["title"], ch, has_content))

        if not chapter_list:
            QMessageBox.warning(self, "提示", "未找到章节")
            return

        # 弹出勾选对话框
        dlg = QDialog(self)
        dlg.setWindowTitle("批量写章节")
        dlg.setMinimumWidth(400)
        dlg.setMinimumHeight(350)
        vbox = QVBoxLayout(dlg)
        vbox.addWidget(QLabel("勾选要生成的章节（已有内容的章节将被覆盖）："))

        list_widget = QListWidget()
        for vol_title, ch, has_content in chapter_list:
            mark = "✓" if has_content else "○"
            item = QListWidgetItem(f"{mark}  {vol_title} / {ch['title']}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if has_content else Qt.Checked)
            item.setData(Qt.UserRole, ch["id"])
            list_widget.addItem(item)
        vbox.addWidget(list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        vbox.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        # 收集勾选的章节 ID
        selected_ids = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_ids.append(item.data(Qt.UserRole))

        if not selected_ids:
            return

        # 启动批量模式
        self._batch_queue = selected_ids
        self._batch_total = len(selected_ids)
        self._batch_done = 0
        self._batch_failed = 0
        self._batch_mode = True
        self.batch_progress.setMaximum(self._batch_total)
        self.batch_progress.setValue(0)
        self.batch_progress.setVisible(True)
        self.batch_label.setText(f"进度: 0/{self._batch_total}")
        self.batch_label.setVisible(True)
        self.btn_batch.setEnabled(False)
        self.btn_write_ch1.setEnabled(False)
        self.btn_outline.setEnabled(False)

        self._write_next_in_batch()

    def _write_next_in_batch(self):
        if not self._batch_queue:
            self._finish_batch()
            return

        chapter_id = self._batch_queue.pop(0)
        chapter = self.project.db.get_chapter(chapter_id)
        if chapter:
            self._start_write_chapter(chapter)
        else:
            self.output.append(f"\n\n[错误] 章节不存在（ID: {chapter_id}）")
            self._advance_batch(success=False)

    def _advance_batch(self, success=True):
        self._batch_done += 1
        if not success:
            self._batch_failed += 1

        self.batch_progress.setValue(self._batch_done)
        self.batch_label.setText(
            f"进度: {self._batch_done}/{self._batch_total}（失败: {self._batch_failed}）"
        )

        if self._batch_queue:
            QTimer.singleShot(800, self._write_next_in_batch)
        else:
            self._finish_batch()

    def _finish_batch(self, stopped=False):
        self._batch_mode = False
        self._batch_queue.clear()
        self.batch_progress.setVisible(False)
        self.batch_label.setVisible(False)
        self.btn_batch.setEnabled(True)
        self.btn_write_ch1.setEnabled(True)
        self.btn_outline.setEnabled(True)

        ok_count = max(0, self._batch_done - self._batch_failed)
        if stopped:
            self.output.append(
                f"\n\n=== 批量生成已停止（完成: {self._batch_done}/{self._batch_total}，成功: {ok_count}，失败: {self._batch_failed}） ==="
            )
        else:
            self.output.append(
                f"\n\n=== 批量生成完成（完成: {self._batch_done}/{self._batch_total}，成功: {ok_count}，失败: {self._batch_failed}） ==="
            )
    # ── 对话模式 ──
    def set_chat_chapter_id(self, chapter_id):
        self._chat_chapter_id = chapter_id

    def _send_chat(self):
        if not self.project:
            QMessageBox.information(self, "提示", "请先新建或打开项目")
            return
        if not self.ai_tasks:
            self._init_ai_tasks()
        if not self.ai_tasks or not self.ai_tasks.client.is_configured:
            QMessageBox.warning(self, "提示", "请先配置 AI")
            self.show_settings()
            return

        user_text = self.chat_input.toPlainText().strip()
        if not user_text:
            return

        # 显示用户消息
        self.chat_display.append(f"<b>你:</b> {user_text}\n")
        self.chat_input.clear()

        # 添加到历史
        self._chat_history.append({"role": "user", "content": user_text})

        # 构建消息并发送
        msgs = self.ai_tasks.build_chat_messages(
            self._chat_history, self._chat_chapter_id
        )
        self._chat_accumulated = ""
        self.chat_display.append("<b>AI:</b> ")
        self.btn_send.setEnabled(False)

        self._chat_worker = AIWorker(self.ai_tasks.chat_stream(msgs))
        self._chat_worker.chunk_received.connect(self._on_chat_chunk)
        self._chat_worker.finished_signal.connect(self._on_chat_finished)
        self._chat_worker.error_signal.connect(self._on_chat_error)
        self._chat_worker.start()

    def _on_chat_chunk(self, text):
        self._chat_accumulated += text
        # 更新最后一行的 AI 回复
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.chat_display.setTextCursor(cursor)
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_chat_finished(self):
        self.btn_send.setEnabled(True)
        if self._chat_accumulated:
            self._chat_history.append({
                "role": "assistant",
                "content": self._chat_accumulated,
            })
        self.chat_display.append("\n")

    def _on_chat_error(self, msg):
        self.btn_send.setEnabled(True)
        self.chat_display.append(f"\n<b>[错误]</b> {msg}\n")

    def _clear_chat(self):
        self._chat_history.clear()
        self._chat_accumulated = ""
        self.chat_display.clear()


