# Technical Deep Dive: Real-Time Audio Transcription HUD

This document tracks the design decisions, failed experiments, and benchmark data behind this project — what was tried, what broke, and why.

## System Overview

Captures live Windows system audio via WASAPI loopback, buffers it into chunks, runs it through a local Whisper model on GPU, and displays the result in a transparent always-on-top overlay. Finalized transcripts are dual-written to SQLite for chronological logging and to ChromaDB for semantic vector search.

```
[Windows Speakers] -> (WASAPI Loopback) -> [Thread-safe Queue] -> [NumPy Resample/Downmix]
                                                                        |
                                                              [Dual-Layer VAD Pipeline]
                                                                        |
                                                              [Faster-Whisper (CUDA)]
                                                                        |
                                          +-----------------------------+-----------------------------+
                                          v                                                           v
                               [PyQt6 HUD + SQLite Log]                                     [ChromaDB Vector Store]
                                          |                                                           |
                                  (On Exit / Ctrl+C)                                         (CLI: search.py)
                                          v                                                           v
                                [Groq LLM Summarizer]                                      [Local Semantic Search]
                                          |                                                           |
                               [summaries/summary_XYZ.md]                                  (Optional: RAG with LLM)
```

Audio arrives in 512-frame chunks at 48kHz (~10.66ms each) and is accumulated into a "bucket" before inference, since transcribing every 10ms chunk individually gives the model no usable context.

## Early Experiments

**Rolling context prompting** — passed the previous sentence back into Whisper as an `initial_prompt` for grammatical memory across buckets. Helped at 6s buckets (34.15% -> 31.71% WER) but hurt badly at 1.5s buckets (46.34% -> 51.22%). Cause: fixed-timer cuts routinely slice words in half ("Privet" -> "Priv-" / "-vet"), and feeding that fragment back as a prompt made the model force a grammatically plausible bridge instead of discarding the garbage — producing stuttering and repetition. Memory made it more confidently wrong, not less.

**RMS volume gate** — skipped inference below a volume threshold to save compute. Caused a "hung buffer" deadlock: WASAPI stops sending frames entirely during silence (no frames sent at all), so a short sentence followed by silence sat trapped in the bucket, un-transcribed, until new audio pushed the buffer over the line.

**Production design (v2.0)** — stateless 2.1s buckets, no volume gating, SQLite logging. Prioritized reliability over accuracy gains from heuristics that broke under real conditions.

## Regression Hunt (August 2026)

Reran the original benchmark suite two weeks later with no code changes and got WER 43.9% (was ~30%) and inference time 2.47s (was ~150ms). Traced it in order: suspected GPU fallback -> restarted the machine (inference dropped to 1.42s, but E2E latency rose to 3.21s, pointing to a second stacked issue) -> isolated the model call in a standalone script -> found the solution:Switching to `base.en` dropped inference to 0.47s.

Side finding: switching from `beam_size=1` to `beam_size=5` made WER worse (41.0% -> 53.0%), which is backwards for beam search. Likely cause: greedy decoding on a boundary-cut fragment produces an obviously wrong guess, while beam search optimizes for fluency and confidently "completes" the same fragment into something smooth but wrong — the same failure mode as the context-prompting experiment, triggered by decoding strategy instead of a prompt.

## Two-Layer VAD (v2.5)

Replaced the RMS gate with two components that solve different halves of the problem: an energy gate with a max-wait flush controls *when* the bucket flushes (fixes the deadlock — silence can't trap the buffer), and Faster-Whisper's built-in Silero neural VAD trims residual noise from *what* gets sent to the model. Energy gate alone: 29.27% WER. Both together: 26.83% WER, 0.32s inference, ~0.56s perceived lag (measured from end-of-speech, not from bucket-start).

## Interim Transcription and UI Polish (v2.7)

To bridge the gap between how fast someone speaks and when VAD confirms a pause, the background thread now takes a snapshot of the actively growing bucket every ~190ms (18 chunks) and runs a fast inference pass on it. These snapshots emit to the UI with `is_final=False` — the overlay updates its active line, but SQLite ignores them so drafts never pollute the log. Once VAD detects a real pause, a final `is_final=True` pass locks the text into UI history, writes it to SQLite, and clears the bucket. The overlay reconciles the stream of drafts using a rolling word buffer with prefix-matching deduplication, so the handoff from draft to final doesn't stutter on the boundary word. A 5-second silence watchdog also resets the HUD to "Listening..." during prolonged silence.

## Automated Meeting Summarization (v2.7)

An automated summarizer hooks into the app's shutdown lifecycle (`aboutToQuit` / Ctrl+C): it pulls the session's transcript from SQLite and sends it to the Groq API (`openai/gpt-oss-120b` / Llama 3.3) to generate a structured Markdown report — executive summary, key decisions, action items — with the full raw transcript attached as an appendix. Reports save to the git-ignored `summaries/summary_<session_id>.md`. A standalone `summarizer.py` CLI can list past sessions (`--list`) or regenerate a summary for any of them on demand.

## Local Semantic Search and RAG (v3.0)

To let users query past transcripts without reading full logs, `database.py` now writes each finalized sentence to both SQLite (sequential logging) and ChromaDB (vector search), embedding it locally via `sentence-transformers` (`all-MiniLM-L6-v2`, 384 dimensions, fully offline). The `search.py` CLI supports two modes: pure semantic search (cosine-distance matching, no network calls) and full RAG, which injects the top retrieved matches into a Groq-backed prompt for a synthesized answer.

One real limitation surfaced during testing: without metadata filtering, the vector store retrieves conflicting statements made months apart with no sense of recency, which confuses the LLM in RAG mode. Fixing this properly would mean adding time-decay weighting or a knowledge-graph layer — meaningfully more complexity than a single-user local tool needs. Rather than chase that, this was left as a known limitation and development on search stopped here.

## Benchmark Log

| Date       | Model    | Compute | Beam | Bucket            | WER    | Inference | Pipeline E2E | Perceived Lag | Notes                                |
| ---------- | -------- | ------- | ---- | ----------------- | ------ | --------- | ------------ | ------------- | ------------------------------------ |
| 2026-08-01 | small.en | int8    | 1    | 1.5s              | 46.34% | ~150ms    | ~1.65s       | -             | reading-voice clip, no context       |
| 2026-08-01 | small.en | int8    | 1    | 1.5s              | 51.22% | ~150ms    | ~1.65s       | -             | reading-voice clip, with context     |
| 2026-08-01 | small.en | int8    | 1    | 6.0s              | 34.15% | ~350ms    | ~6.35s       | -             | natural-speech clip, no context      |
| 2026-08-01 | small.en | int8    | 1    | 6.0s              | 31.71% | ~350ms    | ~6.35s       | -             | natural-speech clip, with context    |
| 2026-08-01 | small.en | int8    | 1    | 2.1s              | 30.00% | ~150ms    | ~2.25s       | -             | original baseline                    |
| 2026-08-17 | small.en | int8    | 1    | 2.1s              | 43.90% | ~2470ms   | ~2.71s       | -             | unexplained regression               |
| 2026-08-17 | small.en | int8    | 1    | 2.1s              | -      | ~1420ms   | ~3.21s       | -             | after restart, JIT recompilation     |
| 2026-08-17 | base.en  | int8    | 1    | 2.1s              | 41.00% | ~470ms    | ~2.55s       | -             | model size fix (small.en -> base.en) |
| 2026-08-17 | base.en  | int8    | 5    | 2.1s              | 53.00% | ~530ms    | ~2.13s       | -             | beam=5, boundary penalty             |
| 2026-08-18 | base.en  | int8    | 5    | VAD (energy)      | 29.27% | ~390ms    | ~3.28s       | -             | energy VAD w/ max-wait flush         |
| 2026-08-18 | base.en  | int8    | 5    | Dual VAD          | 26.83% | ~320ms    | ~3.26s       | ~0.56s        | production v2.5 build                |
| 2026-08-18 | base.en  | int8    | 5    | Dual VAD + Stream | 26.85% | ~160ms    | ~3.37s       | ~0.36s        | production v2.7 build                |

*Inference time in v2.7 (~160ms) is a weighted average across ~100ms interim drafts and ~320ms final commits — the two-pass streaming approach lowers the average even though each individual final pass costs the same as before.*

*The 2026-08-01 and 2026-08-17 runs were measured on different environments (driver/library state had drifted between them) and aren't a like-for-like comparison — they're kept as a historical record, not a clean before/after.*

## Resolved

- **Automated meeting summarization** — Groq API integration compiles structured reports on exit, saved to `summaries/`.
- **UI auto-clear timer** — 5s silence watchdog in `overlay.py` resets the HUD during inactive periods.
- **Local semantic search** — `search.py` uses local vector embeddings (`sentence-transformers` + `chromadb`) to query past transcripts offline, with optional RAG synthesis via Groq. Known limitation: no temporal weighting yet, so old and new statements on the same topic can be retrieved with equal relevance.