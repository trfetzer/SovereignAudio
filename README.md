# SovereignAudio (shareable copy)

This folder is a clean copy of the app with no audio, transcripts, or embeddings. All data stays local when you run it.

## Prerequisites
- Python 3.10+
- FFmpeg  
  - macOS: `brew install ffmpeg`  
  - Debian/Ubuntu: `sudo apt install ffmpeg`  
  - Windows: `choco install ffmpeg` or download FFmpeg zip and add `bin/` to PATH
- Node 18+ (for building the frontend)
- Optional: GPU drivers/CUDA for faster WhisperX and Ollama models
- **Ollama** for local embeddings/summaries (see below)

## Set up Python environment (uv preferred)
- Install uv  
  - macOS/Linux: `curl -Ls https://astral.sh/uv/install.sh | sh`  
  - Windows (PowerShell): `Set-ExecutionPolicy Bypass -Scope Process -Force; iwr https://astral.sh/uv/install.ps1 | iex`
- Create/env + install deps (from this folder):  
  - `uv sync` (creates .venv and installs from pyproject/uv.lock)  
  - If you prefer venv + pip:  
    - macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`  
    - Windows: `py -3 -m venv .venv && .\\.venv\\Scripts\\activate`  
    - then `python -m pip install -U pip && python -m pip install soundfile pydub numpy librosa torch whisperx resemblyzer requests fastapi uvicorn python-multipart`

## Local LLM (Ollama) for embeddings and summaries
- Install Ollama:
  - macOS/Linux: `curl -fsSL https://ollama.com/install.sh | sh`
  - Windows: use the Ollama installer from https://ollama.com/download
- Start Ollama: `ollama serve`
- Pull models:
  - Embeddings (default in this repo): `ollama pull mxbai-embed-large`
  - Summaries (match `summary_model` in settings): for example `ollama pull llama3`
- Keep Ollama running while the app runs. You can change `OLLAMA_URL`, `OLLAMA_EMBED_MODEL`, and `summary_model` in `config.py`/`settings.json` or via the Settings page.

## Frontend setup
- `cd frontend`
- `npm install`
- Build static bundle: `npm run build` (outputs to `frontend/dist`)
- Dev mode: `VITE_API_BASE=http://localhost:8000 npm run dev -- --host --port 5173`

## Run the backend
- Activate the venv, then from the repo root:
  - `uvicorn server:app --host 0.0.0.0 --port 8000`
- Open `http://localhost:8000` (serves the built frontend from `frontend/dist` if present).

## What runs locally
- WhisperX (ASR/diarization) runs locally and can use CPU or GPU.
- Embeddings and summaries call your local Ollama server.
- All audio/transcripts/embeddings stay in the working folder unless you expose the server.

## Data hygiene
- By default, runtime data is stored under `library/`:
  - `library/Inbox/…` — new sessions land here.
  - `library/Folders/<folder>/…` — sessions you drag/drop into folders.
  - `library/Trash/…` — deleted sessions/folders (non-destructive).
  - `library/file_index.db`, `library/vector_index.db` — indexes (rebuildable).
  - `library/settings.json`, `library/vocab.json`.
- You can override the location with `SOV_AUDIO_LIBRARY_ROOT=/path/to/Library`.
- To delete all local data:
  - macOS/Linux: `rm -rf library`
  - Windows (PowerShell): `rmdir /s /q library`
- The folder is recreated automatically on next run.

## Notes
- Configure embedding/summary behavior in `settings.json` or via the Settings page (auto-embed/auto-summarize).
- Speaker clustering happens per conversation; no persistent speaker profiles/voiceprints are written to disk.
- Calendar integration uses a read-only ICS feed URL (Settings → Calendar).
- If exposing the app beyond your machine, put it behind HTTPS and add auth. For local use, keep it on LAN or localhost.
