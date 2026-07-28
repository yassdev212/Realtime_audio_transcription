# 🎙️ Local AI Speech-to-Text HUD

A real-time, GPU-accelerated desktop overlay that transcribes system audio instantly. Built entirely in Python, this tool operates 100% locally for maximum privacy—no cloud APIs, no subscriptions, and no data leaving your machine.

*(Note: Insert a GIF or Screenshot of your glowing PyQt6 pill working on your screen right here!)*

## 🚀 Features
* **Real-Time System Audio Capture:** Bypasses standard microphone inputs by hooking directly into Windows WASAPI Loopback drivers.
* **Low-Latency DSP Pipeline:** Custom NumPy digital signal processing to downmix stereo channels and resample 48kHz audio to 16kHz float32 arrays on the fly.
* **GPU-Accelerated Inference:** Utilizes `faster-whisper` (CTranslate2) on NVIDIA CUDA for sub-300ms speech-to-text processing.
* **Thread-Safe Architecture:** Implements a producer-consumer queue design with PyQt6 Signals to prevent UI-blocking during heavy AI inference.
* **Click-Through UI:** A transparent, always-on-top PyQt6 desktop overlay utilizing Win32 API flags for a seamless, non-intrusive user experience.

## 🧠 System Architecture

```text
[Windows Speakers] -> (WASAPI Driver) -> [Audio Queue]
                                             |
[PyQt6 HUD Thread] <- (Qt Signals) <- [Background Worker Thread]
                                             |
                                    (NumPy DSP Surgery)
                                             |
                                 [Faster-Whisper on CUDA]