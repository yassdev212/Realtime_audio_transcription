import sys
import os
import threading
import numpy as np
from queue import Empty
import signal
from PyQt6.QtCore import QTimer
import time
from summarizer import generate_summary
# Disable HuggingFace warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# PyQt6 Imports
from PyQt6.QtWidgets import QApplication

# Local Project Imports
from audio import start_audio_stream, transform_audio
from engine import transcribe_audio
from overlay import SimpleOverlay, Communicate

# Database
import datetime
from database import init_db
from database import log_sentence
from database import get_session_transcript


def run_audio(comm, session_id):
    stream, audio_queue, p = start_audio_stream()
    print("Live audio stream started...")
    init_db()
    
    bucket = []
    silent_chunks_counter = 0
    chunks_since_last_interim = 0  # <--- Tracks time between live draft passes
    bucket_start_time = None  
    
    global all_pipeline_e2e, all_inference_times, all_response_delays
    all_pipeline_e2e = []
    all_inference_times = []
    all_response_delays = []

    try:
        while True:
            try:
                raw_data = audio_queue.get(timeout=0.5)
            except Empty:
                continue

            clean_chunk = transform_audio(raw_data)
            bucket.append(clean_chunk)
            chunks_since_last_interim += 1
            
            if len(bucket) == 1:
                bucket_start_time = time.perf_counter()

            # --- VAD: Measure Volume ---
            chunk_volume = np.sqrt(np.mean(clean_chunk**2))
            if chunk_volume < 0.015:
                silent_chunks_counter += 1
            else:
                silent_chunks_counter = 0

            # --- TRIGGER 1: FINAL COMMITTED PASS (On Pause or Max Ceiling) ---
            is_pause = (len(bucket) >= 100 and silent_chunks_counter >= 35)
            is_too_long = (len(bucket) >= 400)

            if is_pause or is_too_long:
                full_audio = np.concatenate(bucket)
                silence_lag = silent_chunks_counter * 0.01066
                
                ai_start_time = time.perf_counter()
                text = transcribe_audio(full_audio)
                inference_time = time.perf_counter() - ai_start_time
                
                pipeline_e2e = time.perf_counter() - bucket_start_time
                response_delay = silence_lag + inference_time

                all_pipeline_e2e.append(pipeline_e2e)
                all_inference_times.append(inference_time)
                all_response_delays.append(response_delay)

                if text.strip():

                    # 1. EMIT WITH is_final=True (Locks into history!)
                    comm.text_signal.emit(text, True)
                    log_sentence(session_id, text.strip())

                # Reset everything for the next sentence
                bucket = []
                silent_chunks_counter = 0
                chunks_since_last_interim = 0

            # --- TRIGGER 2: INTERIM DRAFT PASS (While user is actively speaking) ---
            # Every ~35 chunks (~370ms), if there is active audio in the bucket
            elif len(bucket) >= 40 and chunks_since_last_interim >= 35 and silent_chunks_counter < 10:
                full_audio = np.concatenate(bucket)
                text = transcribe_audio(full_audio)

                if text.strip():
                    
                    # 2. EMIT WITH is_final=False (Updates active line without saving to SQL!)
                    comm.text_signal.emit(text, False)

                chunks_since_last_interim = 0

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
    signal.signal(signal.SIGINT, lambda *args: app.quit())

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
        # Generates and saves summary_<session_id>.md silently to disk!
        generate_summary(session_id)
        
        # --- CALCULATE ALL 3 BASELINE AVERAGES ---
        avg_pipeline = sum(all_pipeline_e2e) / len(all_pipeline_e2e) if all_pipeline_e2e else 0
        avg_response = sum(all_response_delays) / len(all_response_delays) if all_response_delays else 0
        avg_ai = sum(all_inference_times) / len(all_inference_times) if all_inference_times else 0
        # -----------------------------------------

        print("\n==================================")
        print("      FINAL SESSION TRANSCRIPT     ")
        print("==================================")
        print(full_transcript)
        print("==================================")
        print(f"Average Pipeline E2E (First Sound -> Text): {avg_pipeline:.2f} seconds")
        print(f"Average Perceived Response Lag (End -> Text): {avg_response:.2f} seconds")
        print(f"Average GPU Inference Time:                 {avg_ai:.2f} seconds")
        print("==================================\n")

    app.aboutToQuit.connect(print_final_transcript)

    # 5. Start Audio Pipeline in Background Thread
    audio_thread = threading.Thread(target=run_audio, args=(comm, session_id), daemon=True)
    audio_thread.start()

    # 6. Start PyQt Main Event Loop
    sys.exit(app.exec())