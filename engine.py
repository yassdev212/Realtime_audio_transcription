from faster_whisper import WhisperModel
import time


model = WhisperModel("base.en", device="cuda", compute_type="int8")

def transcribe_audio(audio_np_array,previous_text=""):
    start_time = time.perf_counter()
    
    
    segments, info = model.transcribe(
        audio_np_array,
        beam_size=5,
        vad_filter=True,
        repetition_penalty=1.2,
        initial_prompt=previous_text)
    text = "".join([segment.text for segment in segments])
    
    
    inference_time = time.perf_counter() - start_time
  
    
    return text