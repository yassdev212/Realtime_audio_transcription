import sys
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QObject
import win32gui, win32con

class Communicate(QObject):
    text_signal = pyqtSignal(str, bool)

class SimpleOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.history = []        # Stores locked-in finalized sentences
        self.active_draft = ""   # Stores the active real-time draft
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 780px wide (compact), 62px tall, centered horizontally
        self.setGeometry(570, 45, 780, 62)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Sleek Glass Container Frame
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(14, 14, 18, 0.88);
                border: 1px solid rgba(0, 255, 0, 0.35);
                border-radius: 12px;
            }
        """)

        box_layout = QHBoxLayout(self.container)
        box_layout.setContentsMargins(22, 0, 22, 0)

        # --- BOLDER, LARGER SINGLE LINE ---
        self.label = QLabel("Listening for speech...", self.container)
        self.label.setStyleSheet("""
            font-size: 24px; 
            font-weight: 600;
            color: #00FF00; 
            background: transparent;
            border: none;
            font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
        """)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(False)

        box_layout.addWidget(self.label)
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)

        self.enable_click_through()

    def enable_click_through(self):
        try:
            hwnd = int(self.winId())
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            styles |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
        except Exception as e:
            print(f"Warning setting click-through: {e}")

    def update_text(self, text, is_final=False):
        text = text.strip()
        if not text:
            return

        if is_final:
            self.history.append(text)
            self.active_draft = ""
            
            # Keep the history list clean so it doesn't eat RAM
            if len(self.history) > 5:
                self.history = self.history[-5:]
        else:
            # Word Deduplication between history tail and draft head
            draft_clean = text
            if self.history:
                last_sentence_words = self.history[-1].lower().split()
                draft_words = text.split()

                if draft_words and last_sentence_words:
                    last_word = last_sentence_words[-1].strip(".,!?-")
                    first_draft_word = draft_words[0].lower().strip(".,!?-")
                    
                    if last_word == first_draft_word and len(draft_words) > 1:
                        draft_clean = " ".join(draft_words[1:])
            
            self.active_draft = draft_clean

        # 1. Combine history + active live draft into one seamless string
        full_display = " ".join(self.history)
        if self.active_draft:
            full_display += (" " if full_display else "") + self.active_draft
        full_display = full_display.strip()

        # 2. Fill the bar until we hit ~70 characters, then slide the old text off
        MAX_LINE_CHARS = 70
        if len(full_display) > MAX_LINE_CHARS:
            trimmed = full_display[-MAX_LINE_CHARS:]
            first_space = trimmed.find(" ")
            if first_space != -1:
                display_text = "..." + trimmed[first_space:]
            else:
                display_text = "..." + trimmed
        else:
            display_text = full_display

        self.label.setText(display_text)