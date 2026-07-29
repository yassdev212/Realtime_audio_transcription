import sys
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QObject
import win32gui, win32con  # <-- Added Win32 imports for click-through

class Communicate(QObject):
    text_signal = pyqtSignal(str)

class SimpleOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.history = []  # Stores recent sentences
        self.init_ui()

    def init_ui(self):
        # 1. Added Qt.Tool flag to prevent the window from clogging your taskbar
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        # 2. Tell PyQt to allow transparent window backgrounds
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setGeometry(400, 50, 800, 80)

        layout = QVBoxLayout()
        self.label = QLabel("Listening for speech...", self)
        
        # 3. Changed background from solid #111111 to semi-transparent RGBA (75% opacity)
        self.label.setStyleSheet("""
            font-size: 22px; 
            color: #00FF00; 
            background-color: rgba(17, 17, 17, 0.75);
            padding: 15px;
            border-radius: 10px;
        """)
        
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(True)
        
        layout.addWidget(self.label)
        self.setLayout(layout)

        # 4. Safely apply Win32 click-through
        self.enable_click_through()

    def enable_click_through(self):
        """Tells Windows to pass all mouse clicks through this window."""
        try:
            hwnd = int(self.winId())
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            styles |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
        except Exception as e:
            print(f"Warning setting click-through: {e}")

    def update_text(self, text):
        text = text.strip()
        if not text:
            return

        self.history.append(text)

        total_chars = sum(len(s) for s in self.history)
        if len(self.history) > 3 or total_chars > 140:
            self.history = [text]

        self.label.setText(" ".join(self.history))