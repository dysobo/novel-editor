import math
from PySide6.QtWidgets import QWidget, QToolTip
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics


# 关系类型 → 颜色映射
RELATION_COLORS = {
    "朋友": QColor(70, 130, 230),
    "敌人": QColor(220, 60, 60),
    "恋人": QColor(230, 100, 170),
    "亲属": QColor(60, 180, 90),
    "师徒": QColor(230, 150, 50),
}
DEFAULT_COLOR = QColor(150, 150, 150)
NODE_RADIUS = 28


class RelationshipGraph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._characters = []   # [{"id":, "name":}, ...]
        self._relationships = []  # [{"id":, "name_a":, "name_b":, ...}, ...]
        self._node_positions = {}  # char_id → QPointF
        self._dragging_id = None
        self._drag_offset = QPointF()
        self.setMouseTracking(True)
        self.setMinimumHeight(250)

    def set_data(self, characters, relationships):
        self._characters = characters
        self._relationships = relationships
        self._layout_nodes()
        self.update()

    def _layout_nodes(self):
        """环形布局"""
        n = len(self._characters)
        if n == 0:
            self._node_positions.clear()
            return
        cx = self.width() / 2
        cy = self.height() / 2
        radius = min(cx, cy) - NODE_RADIUS - 20
        if radius < 40:
            radius = 40
        for i, ch in enumerate(self._characters):
            cid = ch["id"]
            if cid not in self._node_positions:
                angle = 2 * math.pi * i / n - math.pi / 2
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                self._node_positions[cid] = QPointF(x, y)

    def resizeEvent(self, event):
        # 重新布局时保留已拖拽的位置
        old_positions = dict(self._node_positions)
        self._node_positions.clear()
        self._layout_nodes()
        # 恢复手动拖拽过的节点位置（按比例缩放）
        self.update()

    def paintEvent(self, event):
        if not self._characters:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制连线
        for rel in self._relationships:
            a_id = rel["character_a_id"]
            b_id = rel["character_b_id"]
            if a_id not in self._node_positions or b_id not in self._node_positions:
                continue
            pa = self._node_positions[a_id]
            pb = self._node_positions[b_id]
            color = RELATION_COLORS.get(rel["relation_type"], DEFAULT_COLOR)
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.drawLine(pa, pb)

            # 连线中点绘制关系类型标签
            mid = (pa + pb) / 2
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.drawText(mid.x() - 15, mid.y() - 4, rel["relation_type"])

        # 绘制节点
        font = QFont("Microsoft YaHei", 9)
        painter.setFont(font)
        fm = QFontMetrics(font)
        for ch in self._characters:
            cid = ch["id"]
            if cid not in self._node_positions:
                continue
            pos = self._node_positions[cid]
            # 圆形节点
            painter.setPen(QPen(QColor(80, 80, 80), 2))
            painter.setBrush(QBrush(QColor(240, 240, 255)))
            painter.drawEllipse(pos, NODE_RADIUS, NODE_RADIUS)
            # 名字
            name = ch["name"]
            tw = fm.horizontalAdvance(name)
            painter.setPen(QColor(30, 30, 30))
            painter.drawText(
                int(pos.x() - tw / 2),
                int(pos.y() + fm.ascent() / 2 - 1),
                name,
            )
        painter.end()

    def _hit_test(self, pos):
        """检测鼠标点击了哪个节点"""
        for ch in self._characters:
            cid = ch["id"]
            if cid in self._node_positions:
                node_pos = self._node_positions[cid]
                dx = pos.x() - node_pos.x()
                dy = pos.y() - node_pos.y()
                if dx * dx + dy * dy <= NODE_RADIUS * NODE_RADIUS:
                    return cid
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            cid = self._hit_test(event.position())
            if cid is not None:
                self._dragging_id = cid
                self._drag_offset = self._node_positions[cid] - event.position()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_id is not None:
            self._node_positions[self._dragging_id] = event.position() + self._drag_offset
            self.update()
        else:
            # 悬停提示
            cid = self._hit_test(event.position())
            if cid is not None:
                tips = []
                for rel in self._relationships:
                    if rel["character_a_id"] == cid or rel["character_b_id"] == cid:
                        tips.append(f"{rel['name_a']} ↔ {rel['name_b']}: {rel['relation_type']}")
                        if rel["description"]:
                            tips[-1] += f" ({rel['description']})"
                if tips:
                    QToolTip.showText(event.globalPosition().toPoint(), "\n".join(tips))
                else:
                    QToolTip.hideText()
            else:
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging_id = None
        super().mouseReleaseEvent(event)
