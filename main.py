import sys
import os
import threading
import numpy as np
from queue import Empty

# Disable HuggingFace warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# PyQt6 Imports
from PyQt6.QtWidgets import QApplication

# Local Project Imports
from audio import start_audio_stream, transform_audio
from engine import transcribe_audio
from overlay import SimpleOverlay, Communicate


def run_audio(comm):
    """Background worker function that captures audio, cleans it, and calls Whisper."""
    stream, audio_queue, p = start_audio_stream()
    print("Live audio stream started...")
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

            # 2. Process every ~1.5 seconds of audio (140 chunks)
            if len(bucket) >= 140:
                full_audio = np.concatenate(bucket)
                text = transcribe_audio(full_audio)

                if text.strip():
                    print(f"Detected: {text}")
                    # 3. Emit signal to update PyQt GUI safely across threads
                    comm.text_signal.emit(text)

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

    # 2. Create Window and Signal Communicator
    overlay = SimpleOverlay()
    overlay.show()

    comm = Communicate()
    comm.text_signal.connect(overlay.update_text)

    # 3. Start Audio Pipeline in Background Thread
    audio_thread = threading.Thread(target=run_audio, args=(comm,), daemon=True)
    audio_thread.start()

    # 4. Start PyQt Main Event Loop
    sys.exit(app.exec())