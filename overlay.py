import sys
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QObject

class Communicate(QObject):
    text_signal = pyqtSignal(str)

class SimpleOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.history = []  # <--- Stores recent sentences
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        self.setGeometry(400, 50, 800, 80)

        layout = QVBoxLayout()
        self.label = QLabel("Listening for speech...", self)
        
        self.label.setStyleSheet("""
            font-size: 22px; 
            color: #00FF00; 
            background-color: #111111;
            padding: 15px;
            border-radius: 10px;
        """)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setWordWrap(True)
        
        layout.addWidget(self.label)
        self.setLayout(layout)

    def update_text(self, text):
        text = text.strip()
        if not text:
            return

        # 1. Add new sentence to history
        self.history.append(text)

        # 2. Keep up to 3 sentences or ~140 characters before clearing
        total_chars = sum(len(s) for s in self.history)
        if len(self.history) > 3 or total_chars > 140:
            self.history = [text]

        # 3. Join sentences with a dot
        self.label.setText("".join(self.history))