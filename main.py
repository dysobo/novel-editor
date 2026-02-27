import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile, QTextStream
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("小说编辑器")

    # 加载主题
    style_path = os.path.join(os.path.dirname(__file__), "resources", "styles", "theme.qss")
    if os.path.exists(style_path):
        f = QFile(style_path)
        if f.open(QFile.ReadOnly | QFile.Text):
            stream = QTextStream(f)
            app.setStyleSheet(stream.readAll())
            f.close()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
