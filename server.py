import io
import json
import os
import sqlite3
import uuid
import time
import asyncio
import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
import soundfile as sf
import librosa
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import (
    DB_PATH,
    EMBEDDINGS_FOLDER,
    OLLAMA_EMBED_MODEL,
    OLLAMA_URL,
    RECORDINGS_FOLDER,
    TRANSCRIPT_FOLDER,
    SUMMARY_MODEL_FAST,
)
from database import init_db, insert_session, update_embedding, update_transcript, update_session_title, get_session_by_transcript
from diarizer import transcribe_with_diarization, load_pipeline
from embedder import embed_text_file
from voiceprints import load_voiceprints, save_voiceprints

SETTINGS_FILE = "settings.json"
VOCAB_FILE = "vocab.json"

app = FastAPI(title="SovereignAudio API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_dirs():
    for folder in [RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER]:
        os.makedirs(folder, exist_ok=True)
    init_db()


def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_settings():
    return load_json(
        SETTINGS_FILE,
        {
            "asr_model": None,
            "language": "en",
            "embed_model_doc": OLLAMA_EMBED_MODEL,
            "embed_model_query": OLLAMA_EMBED_MODEL,
            "summary_model": SUMMARY_MODEL_FAST,
            "auto_embed": True,
            "auto_summarize": False,
        },
    )


def load_vocab():
    return load_json(VOCAB_FILE, [])


def embed_query(prompt: str, model: Optional[str] = None):
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": model or OLLAMA_EMBED_MODEL, "prompt": prompt},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError("No embedding returned from Ollama.")
    return emb


def generate_summary(text: str):
    settings = load_settings()
    model = settings.get("summary_model") or SUMMARY_MODEL_FAST
    
    prompt = f"""
    You are an expert meeting assistant. Summarize the following transcript.
    Structure your response into these sections:
    1. Topics / Outline
    2. Key Decisions
    3. Action Items (who needs to do what)

    Transcript:
    {text[:20000]} 
    """
    # Truncate to avoid context limit issues for now, though 20k chars is decent.
    
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def maybe_embed_transcript(transcript_path: str, settings: dict) -> Optional[str]:
    """Embed a transcript if enabled; returns embedding path or None."""
    if not settings.get("auto_embed"):
        return None
    emb = embed_text_file(transcript_path)
    if not emb:
        return None
    date_folder = os.path.basename(os.path.dirname(transcript_path))
    out_dir = os.path.join(EMBEDDINGS_FOLDER, date_folder)
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, os.path.basename(emb))
    os.replace(emb, target)
    update_embedding(transcript_path, target)
    return target


def maybe_summarize_transcript(transcript_path: str, settings: dict) -> Optional[str]:
    """Generate a summary if enabled; returns summary path or None."""
    if not settings.get("auto_summarize"):
        return None
    summary_path = os.path.splitext(transcript_path)[0] + ".summary.txt"
    txt = Path(transcript_path).read_text(encoding="utf-8", errors="ignore")
    summary = generate_summary(txt)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)
    return summary_path


def cosine(a, b):
    a = np.array(a)
    b = np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def resolve_transcript_path(session_path: str) -> Optional[str]:
    if not session_path:
        return None
    candidates = []
    if os.path.isabs(session_path):
        candidates.append(session_path)
    candidates.append(os.path.join(TRANSCRIPT_FOLDER, session_path))
    base = os.path.basename(session_path)
    for root, _, files in os.walk(TRANSCRIPT_FOLDER):
        if base in files:
            candidates.append(os.path.join(root, base))
    return next((p for p in candidates if os.path.exists(p)), None)


def resolve_audio_for_transcript(transcript_path: str) -> Optional[str]:
    base = os.path.splitext(os.path.basename(transcript_path))[0].replace("_diarized", "")
    for root, _, files in os.walk(RECORDINGS_FOLDER):
        for f in files:
            if f.startswith(base) and f.lower().endswith((".wav", ".webm", ".mp3", ".m4a", ".ogg", ".flac")):
                return os.path.join(root, f)
    return None


ensure_dirs()

# Load ASR pipeline globally
print("Loading ASR pipeline...")
asr_pipeline, asr_device = load_pipeline()
print("ASR pipeline loaded.")

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/settings")
def get_settings():
    return load_settings()


@app.post("/settings")
def post_settings(payload: dict):
    current = load_settings()
    current.update(payload or {})
    save_json(SETTINGS_FILE, current)
    return current


@app.get("/vocab")
def get_vocab():
    return {"words": load_vocab()}


@app.post("/vocab")
def post_vocab(payload: dict):
    words = payload.get("words", [])
    if not isinstance(words, list):
        raise HTTPException(status_code=400, detail="words must be a list")
    save_json(VOCAB_FILE, words)
    return {"words": words}


@app.get("/sessions")
def sessions():
    rows = []
    if not os.path.exists(DB_PATH):
        return rows
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for row in c.execute(
        "SELECT id, timestamp, title, tags, audio_path, transcript_path, embedding_path FROM sessions ORDER BY id DESC"
    ):
        rows.append(
            {
                "id": row[0],
                "timestamp": row[1],
                "title": row[2],
                "tags": row[3],
                "audio_path": row[4],
                "transcript_path": row[5],
                "embedding_path": row[6],
            }
        )
    conn.close()
    return rows


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    dest_dir = os.path.join(RECORDINGS_FOLDER, "uploaded")
    os.makedirs(dest_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    dest = os.path.join(dest_dir, filename)
    with open(dest, "wb") as f:
        f.write(await file.read())
    insert_session(timestamp=datetime.datetime.utcnow().isoformat(), title=file.filename, tags="upload", audio_path=dest)
    return {"audio_path": dest}


@app.post("/transcribe")
def transcribe(payload: dict):
    audio_path = payload.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=400, detail="audio_path missing or not found")
    settings = load_settings()
    vocab_prompt = " ".join(load_vocab()) or None
    transcript_tmp = transcribe_with_diarization(
        audio_path,
        prompt_name_mapping=False,
        language=payload.get("language") or settings.get("language"),
        asr_model=settings.get("asr_model"),
        initial_prompt=vocab_prompt,
        pipeline=asr_pipeline,
    )
    date_folder = os.path.basename(os.path.dirname(audio_path))
    out_dir = os.path.join(TRANSCRIPT_FOLDER, date_folder)
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, os.path.basename(transcript_tmp))
    os.replace(transcript_tmp, target)
    struct_src = os.path.splitext(transcript_tmp)[0] + ".json"
    if os.path.exists(struct_src):
        os.replace(struct_src, os.path.splitext(target)[0] + ".json")
    update_transcript(audio_path, target)
    embedding_path = maybe_embed_transcript(target, settings)
    summary_path = maybe_summarize_transcript(target, settings)
    return {"transcript_path": target, "embedding_path": embedding_path, "summary_path": summary_path}


@app.post("/embed")
def embed(payload: dict):
    transcript_path = payload.get("transcript_path")
    if not transcript_path or not os.path.exists(transcript_path):
        raise HTTPException(status_code=400, detail="transcript_path missing or not found")
    emb = embed_text_file(transcript_path)
    if emb:
        date_folder = os.path.basename(os.path.dirname(transcript_path))
        out_dir = os.path.join(EMBEDDINGS_FOLDER, date_folder)
        os.makedirs(out_dir, exist_ok=True)
        target = os.path.join(out_dir, os.path.basename(emb))
        os.replace(emb, target)
        update_embedding(transcript_path, target)
        return {"embedding_path": target}
    raise HTTPException(status_code=500, detail="Embedding failed")


@app.get("/transcripts/{session_path:path}")
def get_transcript(session_path: str):
    path = resolve_transcript_path(session_path)
    if not path:
        raise HTTPException(status_code=404, detail="Transcript not found")
    txt = Path(path).read_text(encoding="utf-8", errors="ignore")
    struct_path = os.path.splitext(path)[0] + ".json"
    structured = Path(struct_path).read_text(encoding="utf-8") if os.path.exists(struct_path) else None
    
    # Fetch session metadata
    session = get_session_by_transcript(path)
    title = session["title"] if session else "Untitled Session"
    
    return {"transcript_path": path, "text": txt, "structured": structured, "title": title}

@app.post("/sessions/{session_path:path}/rename")
def rename_session(session_path: str, payload: dict):
    path = resolve_transcript_path(session_path)
    if not path:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    new_title = payload.get("title")
    if not new_title:
        raise HTTPException(status_code=400, detail="Title is required")
        
    updated = update_session_title(path, new_title)
    if updated == 0:
        # Maybe the session record doesn't exist for this transcript path?
        # This can happen if the file was manually added or path mismatch.
        # But we can't easily insert it without more info.
        pass
        
    return {"status": "ok", "title": new_title}


@app.post("/transcripts/{session_path:path}/speakers")
def update_speakers(session_path: str, payload: dict):
    path = resolve_transcript_path(session_path)
    if not path:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    struct_path = os.path.splitext(path)[0] + ".json"
    if not os.path.exists(struct_path):
        raise HTTPException(status_code=400, detail="Structured transcript not found")
    
    updates = payload.get("updates", {})  # { "Speaker_0": "Alice" }
    if not updates:
        return {"status": "no_changes"}

    # Load structured transcript
    with open(struct_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Update segments
    changed = False
    for seg in data.get("segments", []):
        spk = seg.get("speaker")
        if spk in updates:
            seg["speaker"] = updates[spk]
            changed = True
    
    if changed:
        # Save structured
        with open(struct_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Regenerate plain text
        lines = []
        for seg in data["segments"]:
            lines.append(f"[{seg['speaker']}] {seg['text']}")
        new_text = "\n".join(lines)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
            
        # Update voiceprints if applicable
        # This is a simplified approach: we just rename the entry in voiceprints if it matches the old name
        # Ideally we would track voiceprint IDs, but for now we rely on names
        vps = load_voiceprints()
        vp_changed = False
        for old_name, new_name in updates.items():
            # Find if there's a voiceprint with the old name (or if it was a temporary ID)
            # In diarizer.py, we might have assigned "Speaker_X".
            # If we want to associate that embedding with "Alice", we need to find the voiceprint entry.
            # But wait, diarizer.py saves voiceprints with keys like "voice_0", "voice_1".
            # The "name" field inside is what matters.
            
            for vid, info in vps.items():
                if info["name"] == old_name:
                    info["name"] = new_name
                    vp_changed = True
        
        if vp_changed:
            save_voiceprints(vps)

    return {"status": "ok"}


@app.post("/summarize")
def summarize(payload: dict):
    session_path = payload.get("session_path")
    path = resolve_transcript_path(session_path)
    if not path:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Check if summary already exists
    summary_path = os.path.splitext(path)[0] + ".summary.txt"
    if os.path.exists(summary_path) and not payload.get("force", False):
        return {"summary": Path(summary_path).read_text(encoding="utf-8")}
    
    txt = Path(path).read_text(encoding="utf-8", errors="ignore")
    try:
        summary = generate_summary(txt)
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


@app.get("/audio")
def get_audio(transcript_path: str, start: float = 0.0, end: float = 0.0):
    transcript_abs = resolve_transcript_path(transcript_path)
    if not transcript_abs:
        raise HTTPException(status_code=404, detail="Transcript not found")
    audio_path = resolve_audio_for_transcript(transcript_abs)
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio not found")
    
    # Use librosa to load audio (supports more formats like webm via ffmpeg)
    try:
        data, sr = librosa.load(audio_path, sr=None)
    except Exception as e:
        print(f"Error loading audio with librosa: {e}")
        # Fallback to soundfile if librosa fails (though unlikely for webm)
        data, sr = sf.read(audio_path, always_2d=False)

    start_frame = int(max(0, start) * sr)
    end_frame = int(len(data) if end <= 0 else min(len(data), end * sr))
    segment = data[start_frame:end_frame]
    buf = io.BytesIO()
    sf.write(buf, segment, sr, format="WAV")
    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")


@app.post("/search")
def search(payload: dict):
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    threshold = float(payload.get("threshold", 0.75))
    settings = load_settings()
    q_emb = embed_query(prompt, model=settings.get("embed_model_query") or OLLAMA_EMBED_MODEL)
    matches = []
    for root, _, files in os.walk(EMBEDDINGS_FOLDER):
        for f in files:
            if not f.endswith(".json"):
                continue
            emb_path = os.path.join(root, f)
            try:
                with open(emb_path, "r") as ef:
                    emb_data = json.load(ef)
                sim = cosine(q_emb, emb_data["embedding"])
                if sim >= threshold:
                    rel = os.path.relpath(emb_path, EMBEDDINGS_FOLDER)
                    matches.append(
                        {
                            "kind": "file",
                            "similarity": sim,
                            "session_path": rel.replace(".json", ".txt"),
                            "transcript_path": rel.replace(".json", ".txt"),
                            "start": 0.0,
                            "end": 0.0,
                            "snippet": "",
                        }
                    )
            except Exception as exc:
                print(f"[warn] failed reading {emb_path}: {exc}")
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return {"results": matches[:100]}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Create a new session for this live recording
    session_id = uuid.uuid4().hex
    filename = f"live_{session_id}.webm"
    live_dir = os.path.join(RECORDINGS_FOLDER, "live")
    os.makedirs(live_dir, exist_ok=True)
    file_path = os.path.join(live_dir, filename)
    
    # Insert session into DB
    insert_session(timestamp=datetime.datetime.utcnow().isoformat(), title=f"Live Recording {session_id[:8]}", tags="live", audio_path=file_path)
    
    print(f"Started live recording: {file_path}")
    
    try:
        with open(file_path, "wb") as f:
            last_transcribe_time = time.time()
            while True:
                data = await websocket.receive_bytes()
                f.write(data)
                f.flush()
                
                now = time.time()
                if now - last_transcribe_time > 3: # Transcribe every 3 seconds
                    last_transcribe_time = now
                    try:
                        # Run transcription in a separate thread to avoid blocking audio reception
                        # Optimization: Transcribe only the last 30 seconds (Rolling Window)
                        def run_transcription():
                            try:
                                # Get duration (might fail if file is incomplete/locked, but usually works)
                                duration = librosa.get_duration(path=file_path)
                                offset = max(0, duration - 30)
                                # Load audio segment
                                audio, sr = librosa.load(file_path, sr=16000, offset=offset)
                                # Transcribe numpy array
                                return asr_pipeline.transcribe(audio, batch_size=16)
                            except Exception as e:
                                print(f"Transcribe chunk failed: {e}")
                                return {"segments": []}
                        
                        result = await asyncio.to_thread(run_transcription)
                        text = " ".join([seg["text"] for seg in result["segments"]])
                        await websocket.send_text(text)
                    except Exception as e:
                        print(f"Live transcription error: {e}")
                
    except WebSocketDisconnect:
        print(f"Live recording stopped: {file_path}")
        
        # Trigger full pipeline (Diarization + optional Embedding/Summary)
        print("Starting post-processing for live recording...")
        try:
            # 1. Transcribe & Diarize
            settings = load_settings()
            vocab_prompt = " ".join(load_vocab()) or None
            
            # We run this in a thread to not block the server (though we are already in an async handler, 
            # but this is heavy CPU work). Ideally use a background task.
            # For now, we just run it.
            def run_pipeline():
                transcript_tmp = transcribe_with_diarization(
                    file_path,
                    prompt_name_mapping=False,
                    language=settings.get("language"),
                    asr_model=settings.get("asr_model"),
                    initial_prompt=vocab_prompt,
                    pipeline=asr_pipeline,
                )
                
                # Move/Rename transcript to correct folder
                date_folder = os.path.basename(os.path.dirname(file_path)) # 'live'
                # Actually we want to move it to 'transcriptions/live' or similar
                # transcribe_with_diarization saves to TRANSCRIPT_FOLDER (transcriptions/)
                # It returns the path.
                
                # Update DB with transcript path
                update_transcript(file_path, transcript_tmp)
                
                # 2. Optional embed + summary
                maybe_embed_transcript(transcript_tmp, settings)
                maybe_summarize_transcript(transcript_tmp, settings)
                    
                print(f"Post-processing complete for {file_path}")

            await asyncio.to_thread(run_pipeline)
            
        except Exception as e:
            print(f"Error in post-processing: {e}")


frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
