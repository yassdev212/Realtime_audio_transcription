# Real-Time WASAPI Transcription HUD (v2.7)

A real-time, GPU-accelerated desktop overlay that transcribes Windows system audio and logs meetings to a local SQLite database, with optional AI-generated meeting summaries. The core transcription engine runs 100% locally on GPU—no audio leaves your machine.

![HUD Demo](assets/demo2.png)

## Features

- **System Audio Capture:** Captures loopback speaker audio directly using Windows WASAPI drivers (`PyAudioWPatch`).
- **Real-Time Audio Processing:** Uses NumPy array slicing to downmix stereo channels to mono, resample 48kHz to 16kHz, and normalize 16-bit PCM bytes to float32 tensors.
- **Dual-Layer Voice Activity Detection:** A custom Python RMS energy counter detects speech pauses (~370ms) to flush audio dynamically without slicing words in half, while `faster-whisper`'s built-in Silero filter (`vad_filter=True`) strips residual static before inference.
- **GPU-Accelerated Inference:** Runs local `faster-whisper` (CTranslate2) on NVIDIA CUDA (`base.en` int8).
- **Two-Tone Real-Time Streaming:** Live draft words stream to the overlay in real-time, locking in as solid white once speech pauses are confirmed.
- **Persistent SQLite Logging:** Automatically stores transcripts in `transcripts.db`, grouped by unique, timestamped session IDs.
- **Automated Post-Meeting Summaries (Optional):** On exit (`Ctrl+C`), compiles the session transcript and calls an LLM API (Groq) to generate an executive report saved to the `summaries/` directory.
- **Standalone Summarizer CLI:** Run `summarizer.py` to inspect past sessions (`--list`) or generate summaries for any previous session ID on demand.
- **Transparent Click-Through UI:** A borderless, semi-transparent PyQt6 desktop overlay using Win32 API flags (`WS_EX_TRANSPARENT | WS_EX_LAYERED`) so mouse clicks pass directly through to background applications, with a 5-second auto-clear timer on silence.

## System Architecture

```text
[Windows Speakers] ──> (WASAPI Loopback) ──> [Audio Queue]
                                                  │
[PyQt6 HUD Thread] <──   (Qt Signals)   <── [Audio Worker Thread]
  (Click-Through)                                 │
                                         (NumPy Downmix & Resample)
                                                  │
                                         [Dual-Layer VAD Check]
                                                  │
                                      [Faster-Whisper on CUDA]
                                                  │
                                        (Save to SQLite DB)
                                                  │
                                           (On Exit / Ctrl+C)
                                                  ▼
                                         [LLM Summarizer API]
                                                  │
                                      [summaries/summary_XYZ.md]
```

For the full engineering rationale, benchmark comparisons, and failure analysis, see [documentation.md](documentation.md).

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yassdev212/Realtime_audio_transcription.git
cd Realtime_audio_transcription
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Install NVIDIA CUDA runtime libraries (for GPU acceleration):

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

*(Note: On Windows, make sure the installed DLL directories are added to your Python path or placed in the CTranslate2 directory. See `engine.py` for implementation).*

4. Configure your API key (Optional for Summaries):

The core HUD, audio capture, and local transcription are **100% offline and require no API key**.

To enable automated meeting summaries on exit, create a `.env` file in the project root and add an API key (e.g., from [Groq Console](https://console.groq.com/)):

```env
GROQ_API_KEY=gsk_your_api_key_here
```

*(If no key is configured, the program will simply export the full raw database transcript upon exit without crashing).*

## Usage

### 1. Running the Live HUD

Run the main script. Audio will automatically stream as text at the top of your screen:

```bash
python main.py
```

To stop, focus the terminal and press `Ctrl+C`. The application will shut down cleanly, query SQLite for the current session, and save an AI summary to `summaries/summary_<session_id>.md`.

### 2. Standalone Summarizer CLI

You can inspect and summarize any past meeting from the database at any time:

```bash
# List all past sessions stored in SQLite
python summarizer.py --list

# Summarize the most recent session
python summarizer.py

# Summarize a specific session ID
python summarizer.py Session_20260818_143000
```

## Roadmap

- [x] **V1.0:** Core Audio-to-Text HUD Pipeline
- [x] **V2.0:** SQLite persistent session logging and native exit exporter
- [x] **V2.5:** Dual-layer VAD (energy gate + neural Silero filter) — WER 26.83%, inference ~0.32s, perceived lag ~0.56s
- [x] **V2.7:** Automated meeting summaries via LLM API, standalone CLI, live two-tone interim streaming, and 5s UI auto-clear
- [ ] **V3.0:** Standalone local semantic search engine (`search.py`) using local vector embeddings (`sentence-transformers` + `chromadb`) to query past transcripts offline

## License

MIT License. Feel free to use, modify, and learn from this code!
