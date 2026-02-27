from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QToolBar, QComboBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import (
    QAction, QTextCharFormat, QFont, QTextCursor,
    QTextListFormat, QKeySequence,
)


class Editor(QWidget):
    content_changed = Signal()

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        self.toolbar = QToolBar()
        self._init_toolbar()
        layout.addWidget(self.toolbar)

        # 编辑区
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(True)
        self.text_edit.setTabStopDistance(40)
        self.text_edit.textChanged.connect(self.content_changed.emit)
        self.text_edit.cursorPositionChanged.connect(self._update_format_buttons)
        layout.addWidget(self.text_edit)

    def _init_toolbar(self):
        # 标题下拉
        self.heading_combo = QComboBox()
        self.heading_combo.addItems(["正文", "标题1", "标题2", "标题3"])
        self.heading_combo.currentIndexChanged.connect(self._set_heading)
        self.toolbar.addWidget(self.heading_combo)
        self.toolbar.addSeparator()

        # 加粗
        act_bold = QAction("B", self)
        act_bold.setShortcut(QKeySequence("Ctrl+B"))
        act_bold.setCheckable(True)
        act_bold.triggered.connect(self._toggle_bold)
        self.toolbar.addAction(act_bold)
        self._act_bold = act_bold

        # 斜体
        act_italic = QAction("I", self)
        act_italic.setShortcut(QKeySequence("Ctrl+I"))
        act_italic.setCheckable(True)
        act_italic.triggered.connect(self._toggle_italic)
        self.toolbar.addAction(act_italic)
        self._act_italic = act_italic

        # 下划线
        act_underline = QAction("U", self)
        act_underline.setShortcut(QKeySequence("Ctrl+U"))
        act_underline.setCheckable(True)
        act_underline.triggered.connect(self._toggle_underline)
        self.toolbar.addAction(act_underline)
        self._act_underline = act_underline

        self.toolbar.addSeparator()

        # 列表
        act_list = QAction("列表", self)
        act_list.triggered.connect(self._insert_list)
        self.toolbar.addAction(act_list)

        # 分隔线
        act_hr = QAction("—", self)
        act_hr.triggered.connect(self._insert_hr)
        self.toolbar.addAction(act_hr)

    def _post_init_signals(self):
        """在 _init_ui 中 text_edit 创建后调用"""
        self.text_edit.cursorPositionChanged.connect(self._update_format_buttons)

    def _update_format_buttons(self):
        fmt = self.text_edit.currentCharFormat()
        self._act_bold.setChecked(fmt.fontWeight() == QFont.Bold)
        self._act_italic.setChecked(fmt.fontItalic())
        self._act_underline.setChecked(fmt.fontUnderline())

    def _toggle_bold(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if checked else QFont.Normal)
        self._merge_format(fmt)

    def _toggle_italic(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontItalic(checked)
        self._merge_format(fmt)

    def _toggle_underline(self, checked):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(checked)
        self._merge_format(fmt)

    def _merge_format(self, fmt):
        cursor = self.text_edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.text_edit.mergeCurrentCharFormat(fmt)

    def _set_heading(self, index):
        cursor = self.text_edit.textCursor()
        block_fmt = cursor.blockFormat()
        char_fmt = QTextCharFormat()
        if index == 0:  # 正文
            char_fmt.setFontPointSize(14)
            char_fmt.setFontWeight(QFont.Normal)
        elif index == 1:  # 标题1
            char_fmt.setFontPointSize(24)
            char_fmt.setFontWeight(QFont.Bold)
        elif index == 2:  # 标题2
            char_fmt.setFontPointSize(20)
            char_fmt.setFontWeight(QFont.Bold)
        elif index == 3:  # 标题3
            char_fmt.setFontPointSize(16)
            char_fmt.setFontWeight(QFont.Bold)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.mergeCharFormat(char_fmt)
        self.text_edit.mergeCurrentCharFormat(char_fmt)

    def _insert_list(self):
        cursor = self.text_edit.textCursor()
        cursor.insertList(QTextListFormat.ListDisc)

    def _insert_hr(self):
        cursor = self.text_edit.textCursor()
        cursor.insertHtml("<hr/>")

    # ── 公共接口 ──
    def set_content(self, html):
        self.text_edit.blockSignals(True)
        self.text_edit.setHtml(html)
        self.text_edit.blockSignals(False)

    def get_content(self):
        return self.text_edit.toHtml()

    def get_plain_text(self):
        return self.text_edit.toPlainText()

    def get_selected_text(self):
        return self.text_edit.textCursor().selectedText()

    def insert_text(self, text):
        self.text_edit.textCursor().insertText(text)

    def append_text(self, text):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.text_edit.setTextCursor(cursor)

    def clear(self):
        self.text_edit.clear()
