# Real-Time WASAPI Transcription HUD (v2.7)

A real-time, GPU-accelerated desktop overlay that transcribes system audio instantly, logs meetings to a local SQLite database, and automatically generates structured AI meeting summaries. Built in Python, the core transcription engine operates 100% locally for maximum privacy—no cloud APIs, no subscriptions, and no audio leaving your machine.

![HUD Demo](assets/demo2.png)

## Features

- **Real-Time System Audio Capture:** Bypasses standard microphone inputs by hooking directly into Windows WASAPI Loopback drivers (PyAudioWPatch).
- **Low-Latency DSP Pipeline:** Custom NumPy digital signal processing to downmix stereo channels and resample 48kHz audio to 16kHz float32 arrays on the fly.
- **Dual-Layer Voice Activity Detection:** An energy-based gate controls when audio buckets flush (eliminating silent-audio deadlocks), while faster-whisper's built-in Silero neural VAD trims residual noise before inference — together dropping Word Error Rate to 26.83% with ~0.32s inference time and ~0.56s perceived lag.
- **GPU-Accelerated Inference:** Utilizes faster-whisper (CTranslate2) on NVIDIA CUDA for local speech-to-text processing.
- **Persistent Session Logging:** Automatically initializes and writes transcripts to a local SQLite database (transcripts.db), grouping sentences by unique, time-stamped session IDs.
- **Automated AI Meeting Summaries:** Upon closing the HUD, the app compiles the session and generates an executive Markdown report (Executive Summary, Key Decisions, Action Items, and Full Raw Transcript) saved to the `summaries/` directory via an LLM API.
- **Standalone Summarizer CLI:** `summarizer.py` can be executed independently to list past sessions (`--list`) or generate summaries for any previous session ID on demand.
- **Transparent Click-Through UI:** A borderless, semi-transparent PyQt6 desktop overlay utilizing Win32 API flags so mouse clicks pass directly through the text to background apps, with a 5-second auto-clear timer on prolonged silence.

## System Architecture

```text
[Windows Speakers] ──> (WASAPI Driver) ──> [Audio Queue]
                                               │
[PyQt6 HUD Thread] <──  (Qt Signals)  <── [Background Worker Thread]
  (Click-Through)                              │
                                      (NumPy DSP Surgery)
                                               │
                                    [Dual-Layer VAD Filter]
                                               │
                                   [Faster-Whisper on CUDA]
                                               │
                                     (Save to SQLite DB)
                                               │
                                        (On Exit / Ctrl+C)
                                               ▼
                                      [AI Meeting Summarizer]
                                               │
                                   [summaries/summary_XYZ.md]
```

For the full engineering story behind these design decisions — including failure analysis and benchmark logs — see [documentation.md](documentation.md).

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

3. Install NVIDIA CUDA requirements (If using GPU acceleration):

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

*(Note: Windows users may need to explicitly add these DLL paths to their Python script or copy them to the CTranslate2 folder. See engine.py for implementation).*

4. Configure your API key (Optional for Summaries):

The core HUD, audio capture, and transcription are **100% local and require no API key**. 

To enable automated post-meeting AI summaries, create a `.env` file in the project root and add your free API key (e.g., from [Groq Console](https://console.groq.com/)):

```env
GROQ_API_KEY=gsk_your_api_key_here
```

*(If no key is provided, the application will still log everything locally and export the full raw transcript upon exit without crashing).*

## Usage

### 1. Running the Live HUD
Run the main script. Play a video, podcast, or join a meeting, and the transcription will automatically stream on your screen.

```bash
python main.py
```

To exit, focus the terminal and press `Ctrl+C` for a graceful shutdown. This will query the database, print the compiled transcript, and save your AI meeting report to `summaries/summary_<session_id>.md`.

### 2. Standalone Summarizer CLI
You can inspect and summarize any past meeting from SQLite at any time:

```bash
# List all past sessions stored in SQLite
python summarizer.py --list

# Summarize the most recent session
python summarizer.py

# Summarize a specific past session ID
python summarizer.py Session_20260818_143000
```

## Roadmap

- [x] V1.0: Core Audio-to-Text HUD Pipeline
- [x] V2.0: SQLite persistent session logging and native exit exporter
- [x] V2.5: Dual-layer VAD (energy gate + neural Silero filter) — WER down to 26.83%, inference ~0.32s, perceived lag ~0.56s
- [x] V2.7: Automated meeting minutes and action items generator via LLM API, standalone CLI, and 5s UI auto-clear
- [ ] V3.0: Standalone local semantic search engine (`search.py`) using local vector embeddings (sentence-transformers + chromadb) to query past transcripts offline

## License

MIT License. Feel free to use, modify, and learn from this code!
