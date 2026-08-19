# Engineering Notes: Real-Time Audio Transcription HUD

This document tracks the design decisions, failed experiments, and benchmark data behind this project — what was tried, what broke, and why.

---

## System Overview

Captures live Windows system audio via WASAPI loopback, buffers it into chunks, runs it through a local Whisper model on GPU, and displays the result in a transparent always-on-top overlay. Transcripts are logged to SQLite per session.

[Windows Speakers] -> (WASAPI Loopback) -> [Thread-safe Queue] -> [NumPy Resample/Downmix]
                                                                        |
                                                              [Dual-Layer VAD Pipeline]
                                                                        |
                                                              [Faster-Whisper (CUDA)]
                                                                        |
                                                             [PyQt6 HUD + SQLite Log]
                                                                        |
                                                                (On Exit / Ctrl+C)
                                                                        v
                                                               [Groq LLM Summarizer]
                                                                        |
                                                             [summaries/summary_XYZ.md]

Audio arrives in 512-frame chunks at 48kHz (~10.66ms each) and is accumulated into a "bucket" before inference, since transcribing every 10ms chunk individually gives the model no usable context.

---

## Early Experiments

* Rolling Context Prompting:
  Passed the previous sentence back into Whisper as an initial_prompt for grammatical memory across buckets. Helped at 6s buckets (34.15% -> 31.71% WER) but hurt badly at 1.5s buckets (46.34% -> 51.22%).
  Cause: Fixed-timer cuts routinely slice words in half ("Privet" -> "Priv-" / "-vet"). Feeding that fragment back as a prompt made the model force a grammatically plausible bridge instead of discarding garbage, producing stuttering and repetition. Memory made it more confidently wrong, not less.

* RMS Volume Gate:
  Skipped inference below a volume threshold to save compute. Caused a "hung buffer" deadlock: WASAPI stops sending frames entirely during silence (no frames sent at all). A short sentence followed by silence sat trapped in the bucket, un-transcribed, until new audio played to push the buffer over the line.

* Production Design (v2.0):
  Stateless 2.1s buckets, no volume gating, SQLite logging. Prioritized reliability over accuracy gains from heuristics that broke under real conditions.

---

## Regression Hunt (August 2026)

Reran the original benchmark suite two weeks later with no code changes, getting WER 43.9% (was ~30%) and inference time 2.47s (was ~150ms). Traced in order:
1. Suspected GPU fallback.
2. Restarted machine (inference dropped to 1.42s, but E2E latency rose to 3.21s, pointing to stacked issues).
3. Isolated model call in a standalone script.
4. Found fix:Switching to base.en instead dropped inference to 0.47s.

Side finding: Switching from beam_size=1 to beam_size=5 made WER worse (41.0% -> 53.0%). Greedy decoding on a boundary-cut fragment produces an obvious wrong guess; beam search optimizes for fluency and "completes" the fragment into something smooth but wrong (same failure mode as context prompting).

---

## Two-Layer VAD (v2.5)

Replaced the RMS gate with two components solving different halves of the problem:
1. Energy gate with max-wait flush: Controls when the bucket flushes (fixes deadlock; silence cannot trap the buffer).
2. Faster-Whisper built-in Silero neural VAD: Trims residual noise/silence inside the audio sent to the model (vad_filter=True).

Results: Energy gate alone = 29.27% WER. Both together = 26.83% WER, 0.32s inference, ~0.56s perceived lag (measured from speech-end, not bucket-start).

---

## Interim Transcription (Live Drafts) & UI Polish

Upgraded to support real-time interim transcription ("live typing"):
* Growing Snapshots: Background thread takes a snapshot of the growing bucket every ~190ms (18 chunks) for a fast inference pass.
* State Separation: Interim drafts emit with is_final=False to update the active UI text without polluting SQLite. When VAD detects a pause, is_final=True locks text into UI history, writes to SQLite, and clears the bucket.
* Word Deduplication: UI strips duplicate boundary words between consecutive passes.
* Auto-Clear Timer: 5-second single-shot QTimer in overlay.py resets HUD to "Listening..." during prolonged silence.

---

## Automated Meeting Summarization & Session Export (v2.7)

* Architecture: Automated summarizer hooked into shutdown lifecycle (aboutToQuit / Ctrl+C). Queries session_id from SQLite and sends compiled transcript to Groq Cloud API (openai/gpt-oss-120b / Llama 3.3).
* Single-Artifact Export: Generates structured Markdown reports (Executive Summary, Key Decisions, Action Items) with the full raw transcript attached as an appendix.
* File Organization: Reports saved directly into git-ignored summaries/summary_<session_id>.md.
* Standalone CLI: summarizer.py can be run independently to list past sessions (--list) or summarize any past session ID on demand.

---

## Benchmark Log

| Date       | Model    | Compute | Beam | Bucket              | WER    | Inference | Pipeline E2E | Perceived Lag | Notes                                |
| :--------- | :------- | :-----: | :--: | :------------------ | :----: | :-------: | :----------: | :-----------: | :----------------------------------- |
| 2026-08-01 | small.en | int8    | 1    | 1.5s                | 46.34% | ~150ms    | ~1.65s       | -             | reading-voice clip, no context       |
| 2026-08-01 | small.en | int8    | 1    | 1.5s                | 51.22% | ~150ms    | ~1.65s       | -             | reading-voice clip, with context     |
| 2026-08-01 | small.en | int8    | 1    | 6.0s                | 34.15% | ~350ms    | ~6.35s       | -             | natural-speech clip, no context      |
| 2026-08-01 | small.en | int8    | 1    | 6.0s                | 31.71% | ~350ms    | ~6.35s       | -             | natural-speech clip, with context    |
| 2026-08-01 | small.en | int8    | 1    | 2.1s                | 30.00% | ~150ms    | ~2.25s       | -             | original production baseline         |
| 2026-08-17 | small.en | int8    | 1    | 2.1s                | 43.90% | ~2470ms   | ~2.71s       | -             | unexplained regression               |
| 2026-08-17 | small.en | int8    | 1    | 2.1s                | -      | ~1420ms   | ~3.21s       | -             | after restart, JIT recompilation     |
| 2026-08-17 | base.en  | int8    | 1    | 2.1s                | 41.00% | ~470ms    | ~2.55s       | -             | model size fix (small.en -> base.en) |
| 2026-08-17 | base.en  | int8    | 5    | 2.1s                | 53.00% | ~530ms    | ~2.13s       | -             | beam=5, boundary penalty             |
| 2026-08-18 | base.en  | int8    | 5    | VAD (energy)        | 29.27% | ~390ms    | ~3.28s       | -             | energy VAD w/ max-wait flush         |
| 2026-08-18 | base.en  | int8    | 5    | Dual VAD (Energy)   | 26.83% | ~320ms    | ~3.26s       | ~0.56s        | production v2.5 build (VAD baseline) |
| 2026-08-18 | base.en  | int8    | 5    | Dual VAD + Stream   | 26.85% | ~160ms    | ~3.37s       | ~0.36s        | final production v2.7 build          |

### Metric Definitions
* Inference Time (T_inf): Raw execution time of the Whisper model on GPU. In v2.7, ~160ms represents the weighted average across ~100ms interim drafts and ~320ms final commits.
* Pipeline E2E (T_pipeline): Total time from the first audio frame entering the bucket until text renders on the HUD.
* Perceived Response Lag (T_response): Time elapsed from when speech stops until text renders (Pause Confirmation + T_inf = ~0.36s - 0.56s on dual VAD).

Note: The 2026-08-01 and 2026-08-17 numbers were measured on different environments (driver/library state drifted) and are kept as a historical record, not a clean before/after.
Note: Inference in v2.7: ~160ms (Weighted average across ~100ms interim drafts and ~320ms final commits)

## Open Questions / Next Steps

- [x] Automated Meeting Summarization (Resolved): Integrated Groq API to compile structured reports on exit, saved to summaries/.
- [x] UI Auto-Clear Timer (Resolved): Implemented 5s silence watchdog in overlay.py to reset HUD during inactive periods.
- [ ] Local Semantic Search Tool (v3.0 Roadmap): Build standalone CLI search engine (search.py) using local vector embeddings (sentence-transformers + chromadb) to query past transcripts offline without third-party APIs.