from faster_whisper import WhisperModel
from faster_whisper import WhisperModel
import time


model = WhisperModel("small.en", device="cuda", compute_type="int8")

def transcribe_audio(audio_np_array,previous_text=""):
    start_time = time.perf_counter()
    
    
    segments, info = model.transcribe(
        audio_np_array,
        beam_size=1,
        initial_prompt=previous_text)
    text = "".join([segment.text for segment in segments])
    
    
    inference_time = time.perf_counter() - start_time
    print(f"AI took {inference_time:.2f} seconds to think.")
    
    return text