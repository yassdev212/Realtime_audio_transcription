import sys
import win32gui
import win32con
from PyQt6.QtWidgets import QWidget, QLabel, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer  # <-- Added QTimer!
from PyQt6.QtGui import QFont

MAX_WORDS = 14
PILL_WIDTH = 800
PILL_HEIGHT = 60


class Communicate(QObject):
    text_signal = pyqtSignal(str, bool)


class SimpleOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.history_words = []   
        self.draft_words = []     
        
        # --- 5-SECOND AUTO-CLEAR TIMER ---
        self.silence_timer = QTimer(self)
        self.silence_timer.setSingleShot(True)
        self.silence_timer.timeout.connect(self.clear_overlay)
        # ---------------------------------
        
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - PILL_WIDTH) // 2
        self.setGeometry(x, 40, PILL_WIDTH, PILL_HEIGHT)

        self.label = QLabel(self)
        self.label.setGeometry(0, 0, PILL_WIDTH, PILL_HEIGHT)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(False)
        self.label.setTextFormat(Qt.TextFormat.RichText)

        font = QFont()
        font.setFamilies(["Segoe UI Variable", "Segoe UI", "-apple-system"])
        font.setPointSize(14)
        self.label.setFont(font)

        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(20, 20, 22, 180);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: {PILL_HEIGHT // 2}px;
                padding-left: 24px;
                padding-right: 24px;
            }}
        """)

        self.label.setText(self._render_html(["Listening..."], []))
        self.enable_click_through()

    def enable_click_through(self):
        try:
            hwnd = int(self.winId())
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            styles |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
        except Exception as e:
            print(f"Warning setting click-through: {e}")

    def clear_overlay(self):
        """Wipes the bubble when there has been 5 seconds of silence."""
        self.history_words = []
        self.draft_words = []
        self.label.setText(self._render_html(["Listening..."], []))

    def update_text(self, text, is_final=False):
        text = text.strip()
        if not text:
            return

        # Restart the 5-second countdown on every new word!
        self.silence_timer.start(5000)

        words = text.split()

        if is_final:
            if self.history_words and words and words[0] == self.history_words[-1]:
                words = words[1:]
            self.history_words.extend(words)
            self.draft_words = []
        else:
            self.draft_words = words

        combined_len = len(self.history_words) + len(self.draft_words)
        if combined_len > MAX_WORDS:
            overflow = combined_len - MAX_WORDS
            if overflow <= len(self.history_words):
                display_history = self.history_words[overflow:]
                prefix = "... "
            else:
                display_history = []
                remaining_draft_trim = overflow - len(self.history_words)
                self.draft_words = self.draft_words[remaining_draft_trim:]
                prefix = "... "
        else:
            display_history = self.history_words
            prefix = ""

        self.label.setText(self._render_html(display_history, self.draft_words, prefix))

    def _render_html(self, history_words, draft_words, prefix=""):
        history_html = " ".join(history_words)
        draft_html = " ".join(draft_words)

        parts = []
        if prefix:
            parts.append(f'<span style="color: rgba(255,255,255,0.35);">{prefix}</span>')
        if history_html:
            parts.append(f'<span style="color: #FFFFFF;">{history_html}</span>')
        if draft_html:
            separator = " " if history_html else ""
            parts.append(f'<span style="color: rgba(255,255,255,0.5);">{separator}{draft_html}</span>')

        return "".join(parts) if parts else '<span style="color: rgba(255,255,255,0.5);">Listening...</span>'