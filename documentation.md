Engineering Notes: Real-Time Audio Transcription HUD

This document tracks the design decisions, failed experiments, and benchmark data behind this project — what was tried, what broke, and why.

System Overview

Captures live Windows system audio via WASAPI loopback, buffers it into chunks, runs it through a local Whisper model on GPU, and displays the result in a transparent always-on-top overlay. Transcripts are logged to SQLite per session.


[Windows Speakers] ──> (WASAPI Loopback) ──> [Thread-safe Queue] ──> [DSP (resample/downmix)]
                                                                           │
                                                                 [Dual-Layer VAD Pipeline]
                                                                           │
                                                                 [Faster-Whisper (CUDA)]
                                                                           │
                                                                 [PyQt6 Overlay + SQLite Log]
                                                                           │
                                                            (On Exit / Ctrl+C)
                                                                           ▼
                                                                 [Groq LLM Summarizer]
                                                                           │
                                                            [summaries/summary_XYZ.md]


Audio arrives in 512-frame chunks at 48kHz (~10.66ms each) and is accumulated into a "bucket" before inference, since transcribing every 10ms chunk individually would give the model no usable context.

Early Experiments

Rolling context prompting — passed the previous sentence back into Whisper as an initial_prompt for grammatical memory across buckets. Helped at 6s buckets (34.15% -> 31.71% WER) but hurt badly at 1.5s buckets (46.34% -> 51.22%). Cause: fixed-timer cuts routinely slice words in half ("Privet" -> "Priv-" / "-vet"), and feeding that fragment back as a prompt made the model force a grammatically plausible bridge instead of discarding the garbage — producing stuttering and repetition. Memory made it more confidently wrong, not less.

RMS volume gate — skipped inference below a volume threshold to save compute. Caused a "hung buffer" deadlock: WASAPI stops sending frames entirely during silence (not silent frames — no frames), so a short sentence followed by silence would sit trapped in the bucket, un-transcribed, until someone spoke again.

Production design (v2.0): stateless 2.1s buckets, no volume gating, SQLite logging. Prioritized reliability over accuracy gains from heuristics that broke under real conditions.

Regression Hunt (Aug 2026)

Reran the original benchmark suite two weeks later, no code changes, and got WER 43.9% (was ~30%) and inference time 2.47s (was ~150ms). Traced it in order: suspected GPU fallback -> restarted the machine (helped partially, inference dropped to 1.42s, but E2E latency rose, pointing to a second stacked issue) -> isolated the model call from the rest of the pipeline in a standalone script -> found the cause: the model had drifted to small.en on int8/CUDA, and CTranslate2 was silently falling back to a slower compute path rather than erroring. Switching to base.en dropped inference to 0.47s.

Side finding: switching from beam_size=1 to beam_size=5 made WER worse (41.0% -> 53.0%), which is backwards for beam search. Likely cause: greedy decoding on a boundary-cut fragment produces an obviously wrong guess, while beam search optimizes for fluency and confidently "completes" the same fragment into something smooth but wrong — the same failure mode as the context-prompting experiment, triggered by decoding strategy instead of a prompt. Unconfirmed; needs a no-bucketing test to isolate.

Two-Layer VAD

Replaced the RMS gate with two components that solve different halves of the problem: an energy gate with a max-wait flush controls when the bucket flushes (fixes the deadlock — silence can't trap the buffer), and Faster-Whisper's built-in Silero neural VAD trims residual noise/silence from what gets sent to the model. Energy gate alone: 29.27% WER. Both together: 26.83% WER, 0.32s inference, ~0.56s perceived lag (measured from end-of-speech, not from bucket-start).

Interim Transcription (Live Drafts)

To bridge the gap between the user's speaking speed and the VAD flush trigger, the pipeline was upgraded to support real-time interim transcription ("live typing").

Instead of waiting for a pause, the background thread takes a snapshot of the actively growing audio bucket every ~190ms (18 chunks) and runs a fast inference pass.

    State Management: These snapshots are emitted to the PyQt6 thread with an is_final=False flag. The UI updates the active line, but the SQLite database ignores it to prevent pollution.

    The Commit: Once the VAD detects a pause, a final is_final=True pass is executed, locked into UI history, saved to the database, and the bucket is cleared.

    UI Integration: The overlay manages the continuous stream of draft words using a rolling word-based FIFO buffer and simple prefix-matching deduplication to ensure seamless sentence hand-offs on a single line.


    
### Benchmark Log

| Date       | Model    | Compute | Beam  | Bucket                     |  WER   | Inference | Pipeline E2E | Perceived Lag | Notes                                    |
| :--------- | :------- | :-----: | :---: | :------------------------- | :----: | :-------: | :----------: | :-----------: | :--------------------------------------- |
| 2026-08-01 | small.en |  int8   |   1   | 1.5s                       | 46.34% |  ~150ms   |    ~1.65s    |       -       | reading-voice clip, no context prompt    |
| 2026-08-01 | small.en |  int8   |   1   | 1.5s                       | 51.22% |  ~150ms   |    ~1.65s    |       -       | reading-voice clip, with context prompt  |
| 2026-08-01 | small.en |  int8   |   1   | 6.0s                       | 34.15% |  ~350ms   |    ~6.35s    |       -       | natural-speech clip, no context prompt   |
| 2026-08-01 | small.en |  int8   |   1   | 6.0s                       | 31.71% |  ~350ms   |    ~6.35s    |       -       | natural-speech clip, with context prompt |
| 2026-08-01 | small.en |  int8   |   1   | 2.1s                       | 30.00% |  ~150ms   |    ~2.25s    |       -       | original production baseline             |
| 2026-08-17 | small.en |  int8   |   1   | 2.1s                       | 43.90% |  ~2470ms  |    ~2.71s    |       -       | unexplained regression, no code changes  |
| 2026-08-17 | small.en |  int8   |   1   | 2.1s                       |   -    |  ~1420ms  |    ~3.21s    |       -       | after machine restart, still slow        |
| 2026-08-17 | base.en  |  int8   |   1   | 2.1s                       | 41.00% |  ~470ms   |    ~2.55s    |       -       | model size fix (small.en -> base.en)     |
| 2026-08-17 | base.en  |  int8   |   5   | 2.1s                       | 53.00% |  ~530ms   |    ~2.13s    |       -       | beam=5, still bucketed                   |
| 2026-08-18 | base.en  |  int8   |   5   | VAD (energy)               | 29.27% |  ~390ms   |    ~3.28s    |       -       | energy VAD w/ max-wait flush             |
| 2026-08-18 | base.en  |  int8   |   5   | Dual VAD (Energy + Neural) | 26.83% |  ~320ms   |    ~3.26s    |    ~0.56s     | Final production v2.5 build              |

### Metric Definitions
* **Inference Time ($T_{\text{inf}}$):** Raw execution time of the Whisper model on GPU.
* **Pipeline E2E ($T_{\text{pipeline}}$):** Measured from the first audio frame entering the bucket until text is rendered on the HUD.
* **Perceived Response Lag ($T_{\text{response}}$):** Time elapsed from the end of an utterance until text appears ($T_{\text{pause\_confirm}} + T_{\text{inf}} \approx \mathbf{0.62\text{s}}$ on neural VAD).

Note: the 2026-08-01 and 2026-08-17 numbers were measured on different environments (driver/library state had drifted between them) and aren't a like-for-like comparison. They're kept here as a record of what was measured at each point, not as a clean before/after.

Open Questions / Next Steps


- [x] **Automated Meeting Summarization (Resolved):** Integrated Groq API to automatically compile structured markdown reports on session completion with output saved to `summaries/`.
- [x] **UI Auto-Clear Timer (Resolved):** Implemented 5s silence watchdog in `overlay.py` to reset the HUD during inactive periods.
- [ ] **Local Semantic Search Tool (v3.0 Roadmap):** Build a standalone CLI search engine (`search.py`) using local vector embeddings (`sentence-transformers` + `chromadb`) to query past transcripts without sending data to cloud APIs.
