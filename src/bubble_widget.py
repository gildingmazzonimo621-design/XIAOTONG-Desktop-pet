from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPainter, QColor, QFont, QPainterPath, QBrush, QPen

_DESIGN_H = 1440


class BubbleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.text = ""
        self.opacity = 1.0
        self._visible = False
        self._below = False
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self._start_fade)
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._fade_step)
        self.mood = None
        scr = QApplication.primaryScreen()
        _scale = min(1.0, scr.geometry().height() / _DESIGN_H) if scr else 1.0
        self._font_sz = max(7, round(10 * _scale))

    def show_message(self, text, duration=3000, mood=None):
        self.text = text
        self.mood = mood
        self.opacity = 1.0
        self._visible = True
        font = QFont("Microsoft YaHei", self._font_sz)
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text) + 36
        th = fm.height() + 22
        self.setFixedSize(max(tw, 80), th)
        self.show()
        self.update()
        self.hide_timer.stop()
        self.fade_timer.stop()
        self.hide_timer.start(duration)

    def _start_fade(self):
        self.hide_timer.stop()
        self.fade_timer.start(30)

    def _fade_step(self):
        self.opacity -= 0.05
        if self.opacity <= 0:
            self.opacity = 0
            self.fade_timer.stop()
            self._visible = False
            self.hide()
        self.update()

    def paintEvent(self, event):
        if not self._visible or not self.text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.opacity)

        bg = QColor(255, 255, 255, 230)
        pen_color = QColor(180, 190, 210)
        if self.mood is not None:
            m = getattr(self.mood, "name", None) or str(self.mood)
            m = m.lower()
            if "happy" in m or "happ" in m or "\U0001f60a" in m:
                bg = QColor(255, 250, 205, 230)
                pen_color = QColor(200, 170, 80)
            elif "sad" in m or "\U0001f622" in m:
                bg = QColor(235, 245, 255, 230)
                pen_color = QColor(120, 150, 200)
            elif "hungry" in m or "eat" in m or "\U0001f356" in m:
                bg = QColor(255, 245, 235, 230)
                pen_color = QColor(200, 140, 80)
            elif "sleep" in m or "zzz" in m or "\U0001f634" in m:
                bg = QColor(245, 245, 255, 220)
                pen_color = QColor(150, 160, 200)

        br = QRect(4, 4, self.width() - 8, self.height() - 8)
        path = QPainterPath()
        path.addRoundedRect(float(br.x()), float(br.y()),
                            float(br.width()), float(br.height()), 12, 12)

        p.setBrush(QBrush(bg))
        p.setPen(QPen(pen_color, 1.5))
        p.drawPath(path)

        p.setPen(QColor(60, 60, 80))
        p.setFont(QFont("Microsoft YaHei", self._font_sz))
        p.drawText(br, Qt.AlignCenter, self.text)

    def update_position(self, pet_x, pet_y, pet_w):
        bx = int(pet_x + pet_w / 2 - self.width() / 2)
        by_above = int(pet_y - self.height() + 12)
        if by_above < 0:
            by = int(pet_y + pet_w - 12)
            self._below = True
        else:
            by = by_above
            self._below = False
        self.move(bx, by)
