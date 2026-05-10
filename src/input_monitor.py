"""
输入监控模块
监听全局鼠标和键盘事件，向 Qt 主线程发送信号。
新增：
  - 区分鼠标左键/右键按压状态
  - 打字强度分级（轻敲 / 正常 / 激烈）
  - 记录今日统计（键击数、鼠标点击数、滚轮次数）
  - scroll_detected 信号（滚轮）
  - 鼠标移动速度检测
"""
from collections import deque
import time

from PyQt5.QtCore import QObject, pyqtSignal, QTimer

try:
    from pynput import mouse, keyboard
except Exception:
    mouse = None
    keyboard = None


class InputState:
    """当前输入快照，供主渲染循环读取"""

    def __init__(self):
        self._key_times: deque = deque()
        self._mouse_pos: tuple = (0, 0)
        self._prev_mouse_pos: tuple = (0, 0)
        self._left_pressed: bool = False
        self._right_pressed: bool = False

        # 今日统计（程序运行内累计）
        self.today_keystrokes: int = 0
        self.today_mouse_clicks: int = 0
        self.today_scrolls: int = 0
        self._session_start = time.time()

        # 鼠标速度检测
        self._mouse_move_times: deque = deque()
        self._mouse_distances: deque = deque()

    def on_mouse_move(self, x: int, y: int):
        now = time.time()
        px, py = self._mouse_pos
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        self._prev_mouse_pos = self._mouse_pos
        self._mouse_pos = (x, y)
        if dist > 0:
            self._mouse_move_times.append(now)
            self._mouse_distances.append(dist)
            while self._mouse_move_times and now - self._mouse_move_times[0] > 1.0:
                self._mouse_move_times.popleft()
                if self._mouse_distances:
                    self._mouse_distances.popleft()

    def on_mouse_press(self, btn: str):
        if btn == "left":
            self._left_pressed = True
        elif btn == "right":
            self._right_pressed = True
        self.today_mouse_clicks += 1

    def on_mouse_release(self, btn: str):
        if btn == "left":
            self._left_pressed = False
        elif btn == "right":
            self._right_pressed = False

    def on_scroll(self):
        self.today_scrolls += 1

    def on_key_press(self, key: str):
        now = time.time()
        self._key_times.append(now)
        while self._key_times and now - self._key_times[0] > 3.0:
            self._key_times.popleft()
        self.today_keystrokes += 1

    @property
    def mouse_pos(self) -> tuple:
        return self._mouse_pos

    @property
    def left_pressed(self) -> bool:
        return self._left_pressed

    @property
    def right_pressed(self) -> bool:
        return self._right_pressed

    @property
    def any_mouse_pressed(self) -> bool:
        return self._left_pressed or self._right_pressed

    @property
    def typing_speed(self) -> float:
        now = time.time()
        return sum(1 for t in self._key_times if now - t <= 1.0)

    @property
    def is_typing(self) -> bool:
        now = time.time()
        return bool(self._key_times and now - self._key_times[-1] < 2.0)

    @property
    def typing_intensity(self) -> str:
        spd = self.typing_speed
        if spd == 0:
            return "idle"
        elif spd <= 3:
            return "light"
        elif spd <= 7:
            return "normal"
        else:
            return "intense"

    @property
    def mouse_speed(self) -> float:
        return sum(self._mouse_distances)

    @property
    def is_mouse_moving(self) -> bool:
        if not self._mouse_move_times:
            return False
        return time.time() - self._mouse_move_times[-1] < 0.5

    @property
    def session_minutes(self) -> int:
        return int((time.time() - self._session_start) / 60)

    @property
    def session_seconds(self) -> float:
        return time.time() - self._session_start


class InputMonitor(QObject):
    mouse_moved    = pyqtSignal(int, int)
    mouse_pressed  = pyqtSignal(str)
    mouse_released = pyqtSignal(str)
    mouse_scrolled = pyqtSignal()
    key_pressed    = pyqtSignal(str)
    input_idle     = pyqtSignal()

    def __init__(self, idle_timeout: float = 10.0, parent=None):
        super().__init__(parent)
        self.idle_timeout = float(idle_timeout)
        self._last_event  = time.time()
        self._running     = False
        self._mouse_listener   = None
        self._key_listener     = None

        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(500)
        self._idle_timer.timeout.connect(self._check_idle)

    def start(self):
        if self._running:
            return
        self._running = True
        self._idle_timer.start()
        if mouse is None or keyboard is None:
            return

        def on_move(x, y):
            self._last_event = time.time()
            try:
                self.mouse_moved.emit(int(x), int(y))
            except Exception:
                pass

        def on_click(x, y, button, pressed):
            self._last_event = time.time()
            name_map = {"left": "left", "right": "right", "middle": "middle"}
            raw = getattr(button, "name", str(button)).lower()
            name = name_map.get(raw, raw)
            try:
                if pressed:
                    self.mouse_pressed.emit(name)
                else:
                    self.mouse_released.emit(name)
            except Exception:
                pass

        def on_scroll(x, y, dx, dy):
            self._last_event = time.time()
            try:
                self.mouse_scrolled.emit()
            except Exception:
                pass

        def on_key(key):
            self._last_event = time.time()
            try:
                k = getattr(key, "char", None) or str(key)
            except Exception:
                k = str(key)
            try:
                self.key_pressed.emit(k)
            except Exception:
                pass

        self._mouse_listener = mouse.Listener(
            on_move=on_move, on_click=on_click, on_scroll=on_scroll
        )
        self._key_listener = keyboard.Listener(on_press=on_key)
        self._mouse_listener.start()
        self._key_listener.start()

    def stop(self):
        self._running = False
        try:
            self._idle_timer.stop()
        except Exception:
            pass
        try:
            if self._mouse_listener:
                self._mouse_listener.stop()
        except Exception:
            pass
        try:
            if self._key_listener:
                self._key_listener.stop()
        except Exception:
            pass

    def _check_idle(self):
        if time.time() - self._last_event >= self.idle_timeout:
            self.input_idle.emit()
            self._last_event = time.time()
