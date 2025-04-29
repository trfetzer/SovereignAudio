
# 🧠 SovereignAudio: Self-Sovereign Audio Diarization & Transcription

**SovereignAudio** is a local-first Python application that records, transcribes, diarizes, and semantically indexes audio files using speaker voiceprints and embeddings — all without cloud dependencies.

## 🔧 Features
- 📼 Record and import `.mp3` or `.wav` audio
- 🗣️ Diarize speakers using voiceprint embeddings
- ✍️ Transcribe speech to text
- 🔍 Semantic search over transcribed content
- 🧠 Local speaker identity management
- 🖥️ Optional GUI for debugging and testing

## 🗂 Directory Structure
```
SovereignAudio/
├── main.py                 # Entry point
├── config.py               # Settings
├── database.py             # Metadata and transcription store
├── diarizer.py             # Speaker diarization logic
├── embedder.py             # Embedding model interface
├── file_manager.py         # File and directory handling
├── gui_debug.py            # GUI debugger
├── gui_helpers.py          # GUI utilities
├── importer.py             # Audio import logic
├── recorder.py             # Audio recording
├── searcher.py             # Semantic search
├── voiceprints.py          # Voiceprint management
├── embeddings/             # Stored embeddings
├── recordings/
│   └── imported/           # Example audio file
├── transcriptions/         # Output transcriptions
```

## 🚀 Setup Instructions

### 1. Clone the repository or unzip
```bash
unzip SovereignAudio.zip
cd SovereignAudio/SovereignAudio
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install numpy pydub openai-whisper torchaudio transformers faiss-cpu PySimpleGUI
```

### 4. Run the application
```bash
python main.py
```

Optional GUI (debug mode):
```bash
python gui_debug.py
```

## 📂 Add Audio Files
Place `.mp3` or `.wav` files into:
```
recordings/imported/
```

These can then be processed via `importer.py` or the GUI.

## 🔒 Privacy & Sovereignty
- 💾 No data leaves your device
- 📡 No API calls required
- 🧬 Voiceprints stored locally for diarization
