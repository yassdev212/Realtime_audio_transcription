from queue import Queue
import pyaudiowpatch as pyaudio
import numpy as np

CHUNK_SIZE = 512

def transform_audio(raw_bytes):             
    array = np.frombuffer(raw_bytes, dtype=np.int16)
    array = array[::2]
    array = array[::3]
    array = array.astype(np.float32) / 32768
    return array

def start_audio_stream():
    """Finds speakers, opens the WASAPI stream, and returns (stream, queue, pyaudio_instance)."""
    p = pyaudio.PyAudio()
    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
    
    if not default_speakers["isLoopbackDevice"]:
        for loopback in p.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                default_speakers = loopback
                break

    audio_queue = Queue()

    def callback(in_data, frame_count, time_info, status):
        audio_queue.put(in_data) 
        return (None, pyaudio.paContinue)

    stream = p.open(
        format=pyaudio.paInt16,
        channels=default_speakers["maxInputChannels"],
        rate=int(default_speakers["defaultSampleRate"]),
        frames_per_buffer=CHUNK_SIZE,
        input=True,
        input_device_index=default_speakers["index"],
        stream_callback=callback
    )

    return stream, audio_queue, p