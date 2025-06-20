# TranscribeHub – Meeting Transcription & Summarization ,Speaker Statistics & MoM Automation Web App

A powerful Django-based web application that transcribes audio, identifies speakers, analyzes meeting dynamics, and automatically generates Minutes of Meeting (MoM) using state-of-the-art AI models.

---

## 🚀 Key Features

- 🎙️ **Audio Transcription** with OpenAI's Whisper-large-v3
- 🧍 **Speaker Diarization** using pyannote-audio
- 🔐 **OTP-Based Authentication** for secure access
- 🧾 **Speaker Statistics Dashboard**
  - Speaking time per speaker
  - Word count analytics
- 📈 **Interactive Visualizations** with `matplotlib` and `Chart.js`
- 📋 **Automatic MoM Generation** using LLaMA3-based API for LLM-powered summarization

---

## 🧠 Core Functionality

1. **Frontend & Backend Development**  
   - Built responsive UIs with HTML, CSS, Bootstrap  
   - Django-based backend with OTP verification and session handling

2. **AI Model Integration**  
   - `Whisper-large-v3`: Accurate speech-to-text conversion  
   - `pyannote-audio`: Multi-speaker diarization  
   - `LLaMA3`: Summarizes transcripts into actionable insights via API

3. **Transcript-Speaker Alignment**  
   - Custom logic for temporal overlap-based mapping of transcripts to speakers

4. **Meeting Analytics**  
   - Extracts speaker participation metrics (speaking duration, word count)  
   - Renders them with dynamic, clear visual charts

5. **Automated Minutes of Meeting (MoM)**  
   - LLM-powered summarization for extracting:
     - Key discussion points  
     - Action items  
     - Decisions made

---

## 🛠️ Tech Stack

| Layer       | Technology Used                            |
|-------------|---------------------------------------------|
| Framework   | Django (Python)                             |
| Frontend    | HTML, CSS, Bootstrap                        |
| AI Models   | Whisper-large-v3, pyannote-audio, LLaMA3    |
| DB          | SQLite (default)                            |
| Auth        | Django Sessions + OTP via Email             |

---

## ⚙️ Setup Instructions

### 🔽 1. Clone the Repository

```bash
git clone https://github.com/your-username/speaker-statistics-app.git
cd speaker-statistics-app
