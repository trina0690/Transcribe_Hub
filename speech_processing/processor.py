import os
import shutil
import json
import requests
import re
from pathlib import Path
import tempfile
from collections import defaultdict
import requests
import pandas as pd
from pydub import AudioSegment
from pydub.utils import mediainfo
from humanize import naturalsize

from django.conf import settings
from pyannote.audio import Pipeline
from pyannote.core import Segment
from transformers import pipeline

# ----------------------------
# ✅ Sentiment Analysis (Transformers)
# ----------------------------
sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

# def analyze_sentiment(text):
#     try:
#         result = sentiment_analyzer(text[:512])[0]
#         label = result['label']
#         score = result['score']
#         polarity = score if label == "POSITIVE" else -score
#         return label, polarity, None
#     except Exception as e:
#         return "❌ Error", 0, None
def analyze_sentiment(text):
    try:
        result = sentiment_analyzer(text[:512])[0]
        label = result['label']
        score = result['score']
        polarity = score if label == "POSITIVE" else -score

        subjectivity = 0.5  # Neutral default, since HuggingFace doesn’t provide it
        return label, polarity, subjectivity
    except Exception as e:
        return "❌ Error", 0, 0.5  # Even if there's an error, don’t return None


# ----------------------------
# ✅ Prevent symlink issues (especially on Windows)
# ----------------------------
def safe_symlink_to(self, target, target_is_directory=False):
    if target_is_directory:
        shutil.copytree(target, self, dirs_exist_ok=True)
    else:
        shutil.copy2(target, self)

Path.symlink_to = safe_symlink_to
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "true"

# ----------------------------
# ✅ Load Diarization Pipeline
# ----------------------------
def load_diarization_pipeline():
    return Pipeline.from_pretrained(
        "pyannote/speaker-diarization",
        use_auth_token=settings.HUGGINGFACE_AUTH_TOKEN
    )

# ----------------------------
# ✅ Split audio into 60s chunks
# ----------------------------
def split_audio_to_temp_chunks(file_path, chunk_length_ms=60000):  # 60 seconds
    audio = AudioSegment.from_file(file_path)
    chunks = []
    for i in range(0, len(audio), chunk_length_ms):
        chunk = audio[i:i + chunk_length_ms]
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        chunk.export(temp_file.name, format="wav")
        chunks.append(temp_file.name)
    return chunks

# ----------------------------
# ✅ Diarization with Chunking
# ----------------------------
def diarize_audio(file_path):
    pipeline = load_diarization_pipeline()
    audio_chunks = split_audio_to_temp_chunks(file_path)

    full_segments = []
    offset = 0.0

    for chunk_path in audio_chunks:
        diarization = pipeline(chunk_path)
        chunk_audio = AudioSegment.from_file(chunk_path)
        chunk_duration = chunk_audio.duration_seconds

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            full_segments.append({
                "start": round(turn.start + offset, 2),
                "end": round(turn.end + offset, 2),
                "speaker": speaker,
                "text": "..."  # placeholder
            })

        offset += chunk_duration
        os.remove(chunk_path)  # Clean up temp file

    return full_segments

# ----------------------------
# ✅ Transcribe audio using Groq Whisper
# ----------------------------
def transcribe_audio_groq(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            files = {"file": audio_file}
            data = {
                "model": "whisper-large-v3",
                "response_format": "verbose_json"
            }
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers=headers, files=files, data=data
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": f"Transcription failed: {str(e)}"}

# ----------------------------
# ✅ Align transcript with speakers
# ----------------------------
def align_transcript_with_speakers(segments, transcript):
    aligned = []
    for seg in transcript.get("segments", []):
        start, end, text = seg["start"], seg["end"], seg["text"]
        matching_speaker = "Unknown"
        for diar_seg in segments:
            if not (end < diar_seg["start"] or start > diar_seg["end"]):
                matching_speaker = diar_seg["speaker"]
                break
        aligned.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "speaker": matching_speaker,
            "text": text.strip()
        })
    return aligned

# ----------------------------
# ✅ Generate Summary & MoM using Groq LLM
# ----------------------------
def generate_summary_and_mom(transcript_text):
    import requests
    import json
    import re

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = f"""
        You are a helpful assistant that processes meeting transcripts.

        From the following transcript, generate a valid JSON object with two keys:

        1. "summary": A short summary (2-3 sentences) of the meeting.
        2. "mom": An object with:
        - "keyDecisions": a list of key decisions made (or empty list if none).
        - "actionItems": a list of items like: {{ "item": <task>, "assignedTo": <person> }}.
        - "timestamps": a list of timestamped events like: {{ "time": "HH:MM", "event": <description> }}.

        ✅ Only include timestamps **if there is meaningful discussion/context associated** (e.g., what was presented/discussed at that time).  
        ❌ Do not include timestamps that have no event or context.

        ⚠️ Your response must be valid raw JSON only — do NOT include markdown syntax like ```json or ```.

        Transcript:
        {transcript_text}
        """

        # prompt = f"""
        # You are an assistant that reads transcripts of meetings.

        # From the following transcript, generate a JSON object containing:
        # 1. "summary" - a concise overview of the meeting's main points.
        # 2. "mom" - structured Minutes of Meeting with bullet points showing:
        #    - Key decisions
        #    - Action items with assigned persons
        #    - Timestamps if available

        # Return **only valid JSON** with both keys: "summary" and "mom".
        # No markdown or extra commentary.

        # Transcript:
        # {transcript_text}
        # """

        data = {
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        # Raw response from model
        response_text = response.json()["choices"][0]["message"]["content"]
        print("🧠 LLM Output:", response_text)

        # Clean response of markdown-like formatting
        cleaned = re.sub(r"^```json|```$", "", response_text.strip(), flags=re.MULTILINE).strip()

        try:
            result = json.loads(cleaned)

            # Handle missing fields explicitly
            summary = result.get("summary", "Summary not found in response.")
            mom = result.get("mom", "MoM not found in response or was not generated properly.")

            return {
                "summary": summary,
                "mom": mom
            }

        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            return {
                "summary": "Unable to parse summary from LLM response.",
                "mom": response_text  # return full text for debugging
            }

    except Exception as e:
        print(f"❌ LLM API error: {e}")
        return {
            "summary": "Summary generation failed.",
            "mom": f"MoM generation failed: {str(e)}"
        }

# ----------------------------
# ✅ Speaker Stats Table (Pandas)
# ----------------------------
def get_speaker_stats(tagged_segments):
    from collections import defaultdict

    speaker_durations = defaultdict(float)
    speaker_word_counts = defaultdict(int)

    for seg in tagged_segments:
        duration = seg["end"] - seg["start"]
        words = len(seg["text"].split())
        speaker_durations[seg["speaker"]] += duration
        speaker_word_counts[seg["speaker"]] += words

    rows = ""
    for speaker in speaker_durations:
        rows += f"""
        <tr>
            <td>{speaker}</td>
            <td>{speaker_durations[speaker]:.2f}</td>
            <td>{speaker_word_counts[speaker]}</td>
        </tr>
        """


    table_html = f"""
    <style>
        .custom-speaker-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
            font-family: 'Segoe UI', sans-serif;
            font-size: 16px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        .custom-speaker-table th, .custom-speaker-table td {{
            padding: 12px 15px;
            text-align: center;
        }}
        .custom-speaker-table thead {{
            background-color: #4b6cb7;
            background-image: linear-gradient(to right, #182848, #4b6cb7);
            color: white;
        }}
        .custom-speaker-table tbody tr:nth-child(even) {{
            background-color: #f3f3f3;
        }}
        .custom-speaker-table tbody tr:hover {{
            background-color: #e2e8f0;
        }}
        .speaker-stats-caption {{
            text-align: center;
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #2d3748;
        }}
    </style>

    <div class="speaker-stats-caption">🗣️ Speaker Statistics</div>
    <table class="custom-speaker-table">
        <thead>
            <tr>
                <th>Speaker</th>
                <th>Speaking Time (s)</th>
                <th>Word Count</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
    """

    return table_html

# ----------------------------
# ✅ Audio File Info Helper
# ----------------------------
def get_audio_duration_and_size(file_path):
    audio = AudioSegment.from_file(file_path)
    duration = round(audio.duration_seconds, 2)  # Float, safe to use
    size_bytes = os.path.getsize(file_path)      # Integer value in bytes
    size_str = naturalsize(size_bytes)           # e.g., "2.5 MB"
    return size_str, duration, size_bytes        # Return all three

# ----------------------------
# ✅ Count Distinct Speakers
# ----------------------------
def count_speakers(aligned_segments):
    return len(set([seg['speaker'] for seg in aligned_segments if seg.get('speaker')]))
