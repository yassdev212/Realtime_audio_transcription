import sys
import os
import threading
import numpy as np
from queue import Empty
import signal
from PyQt6.QtCore import QTimer


# Disable HuggingFace warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# PyQt6 Imports
from PyQt6.QtWidgets import QApplication

# Local Project Imports
from audio import start_audio_stream, transform_audio
from engine import transcribe_audio
from overlay import SimpleOverlay, Communicate

#database
import datetime
from database import init_db
from database import log_sentence
from database import get_session_transcript


def run_audio(comm, session_id):
    """Background worker function that captures audio, cleans it, and calls Whisper."""
    stream, audio_queue, p = start_audio_stream()
    print("Live audio stream started...")
    # --- DB SETUP (Runs once) ---
    init_db()
    
    
    # ----------------------------
    
    last_text = ""
    bucket = []

    try:
        while True:
            try:
                # Wake up every 0.5s so thread stays responsive
                raw_data = audio_queue.get(timeout=0.5)
            except Empty:
                continue

            # 1. Perform Audio Surgery (Stereo -> Mono, 48kHz -> 16kHz, Float32)
            clean_chunk = transform_audio(raw_data)
            bucket.append(clean_chunk)

            
            # 2. Process every ~2.0 seconds of audio (200 chunks)
            if len(bucket) >= 200:
                full_audio = np.concatenate(bucket)
                
                # Direct, stateless transcription (No gates, no delays!)
                text = transcribe_audio(full_audio)

                if text.strip():
                    print(f"Detected: {text}")
                    comm.text_signal.emit(text)
                    log_sentence(session_id, text.strip())

                bucket = []

    except Exception as e:
        print(f"Audio worker error: {e}")
    finally:
        print("Cleaning up audio stream resources...")
        stream.stop_stream()
        stream.close()
        p.terminate()


if __name__ == "__main__":
    # 1. Initialize PyQt Application
    app = QApplication(sys.argv)

    # --- THE WINDOWS CTRL+C FIX (SYSTEMS LEVEL) ---
    # Catch Ctrl+C and tell the PyQt app to exit cleanly instead of crashing
    signal.signal(signal.SIGINT, lambda *args: app.quit())

    # A tiny 500ms heartbeat timer that forces the C++ loop to yield to Python
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None) 
    # ----------------------------------------------

    # 2. Create Window and Signal Communicator
    overlay = SimpleOverlay()
    overlay.show()

    comm = Communicate()
    comm.text_signal.connect(overlay.update_text)

    # 3. Generate Session ID
    session_id = datetime.datetime.now().strftime("Session_%Y%m%d_%H%M%S")

    # 4. Connect our final print function to Qt's native exit signal
    def print_final_transcript():
        print("\nStopping application...")
        full_transcript = get_session_transcript(session_id)
        print("\n==================================")
        print("      FINAL SESSION TRANSCRIPT     ")
        print("==================================")
        print(full_transcript)
        print("==================================\n")

    app.aboutToQuit.connect(print_final_transcript)

    # 5. Start Audio Pipeline in Background Thread
    audio_thread = threading.Thread(target=run_audio, args=(comm, session_id), daemon=True)
    audio_thread.start()

    # 6. Start PyQt Main Event Loop
    sys.exit(app.exec())