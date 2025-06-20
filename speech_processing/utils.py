import os
import wave
import contextlib

def get_audio_duration_and_size(filepath):
    size = os.path.getsize(filepath)
    size_kb = round(size / 1024, 2)

    try:
        with contextlib.closing(wave.open(filepath, 'r')) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration_sec = round(frames / float(rate), 2)
    except:
        duration_sec = 0.0

    return f"{size_kb} KB", f"{duration_sec} sec"


def count_speakers(transcript):
    return len(set([entry['speaker'] for entry in transcript]))
