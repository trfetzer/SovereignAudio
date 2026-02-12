import io
import json
import os
import re
import shutil
import sqlite3
import time
import asyncio
import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
import soundfile as sf
import librosa
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from calendar_ics import fetch_ics_events, suggest_events
from config import (
    DB_PATH,
    EMBEDDINGS_FOLDER,
    LIBRARY_ROOT,
    OLLAMA_EMBED_MODEL,
    OLLAMA_URL,
    TRANSCRIPT_FOLDER,
    SUMMARY_MODEL_FAST,
)
from database import (
    create_folder,
    delete_folder,
    get_folder_by_dir,
    get_session,
    init_db,
    list_folders,
    list_sessions,
    rename_folder,
    set_session_suggested_titles,
    update_session_folder,
    update_session_paths,
    update_session_title_by_id,
    upsert_session,
)
from diarizer import transcribe_with_diarization, load_pipeline
from embedder import embed_text_file
from library_reconcile import compute_folder_suggestions, reconcile_library
from library_store import (
    create_session_dir,
    ensure_folder_dir,
    ensure_library_dirs,
    folders_root,
    inbox_root,
    library_root,
    load_meta,
    move_session_dir,
    resolve_asset_path,
    save_meta,
    trash_root,
)
from vector_store import search_similar

SETTINGS_FILE = os.path.join(LIBRARY_ROOT, "settings.json")
VOCAB_FILE = os.path.join(LIBRARY_ROOT, "vocab.json")

app = FastAPI(title="SovereignAudio API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

asr_pipeline = None
asr_device = None

def ensure_dirs():
    ensure_library_dirs()
    # Seed runtime settings/vocab from legacy repo-root files (first run migration).
    project_root = Path(__file__).resolve().parent
    if not os.path.exists(SETTINGS_FILE):
        legacy = project_root / "settings.json"
        if legacy.exists():
            os.makedirs(os.path.dirname(SETTINGS_FILE) or ".", exist_ok=True)
            shutil.copy2(str(legacy), SETTINGS_FILE)
    if not os.path.exists(VOCAB_FILE):
        legacy = project_root / "vocab.json"
        if legacy.exists():
            os.makedirs(os.path.dirname(VOCAB_FILE) or ".", exist_ok=True)
            shutil.copy2(str(legacy), VOCAB_FILE)
    for folder in [TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER]:
        os.makedirs(folder, exist_ok=True)
    init_db()
    reconcile_library()
    threshold = float(load_settings().get("folder_suggestion_threshold", 0.78))
    compute_folder_suggestions(threshold=threshold)


def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path: str, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
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
            "title_model": "",
            "auto_embed": True,
            "auto_summarize": False,
            "auto_title_suggest": False,
            "calendar_ics_url": "",
            "calendar_match_window_minutes": 45,
            "folder_suggestion_threshold": 0.78,
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


def generate_title_candidates(text: str, *, calendar: Optional[dict] = None, participants: Optional[list] = None) -> List[str]:
    settings = load_settings()
    model = (settings.get("title_model") or "").strip() or settings.get("summary_model") or SUMMARY_MODEL_FAST

    participants = participants or []
    people = []
    for p in participants:
        if isinstance(p, str):
            people.append(p)
        elif isinstance(p, dict):
            name = p.get("name") or p.get("email")
            if name:
                people.append(str(name))
    people_str = ", ".join(people[:12])

    cal_str = ""
    if calendar:
        cal_title = calendar.get("summary") or calendar.get("title")
        cal_start = calendar.get("start")
        if cal_title:
            cal_str = f"Calendar event: {cal_title}"
            if cal_start:
                cal_str += f" ({cal_start})"

    prompt = f"""
You are naming a voice memo / meeting recording.
Generate 3 short, specific title options (max 8 words each).
Use the transcript content; if the calendar event seems relevant, incorporate it.

{cal_str}
Participants: {people_str}

Transcript (may be partial):
\"\"\"{text[:8000]}\"\"\"

Return ONLY valid JSON in this exact shape:
{{"titles":["...","...","..."]}}
""".strip()

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=300,
        )
        resp.raise_for_status()
        raw = (resp.json().get("response") or "").strip()
    except requests.RequestException as exc:
        detail = str(exc)
        try:
            if getattr(exc, "response", None) is not None:
                detail = f"{detail}: {exc.response.text}"
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Title suggestion failed (Ollama model '{model}'): {detail}")

    candidates: List[str] = []
    try:
        cleaned = raw
        cleaned = re.sub(r"^```(?:json)?\\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        parsed = json.loads(cleaned)
        titles = parsed.get("titles") if isinstance(parsed, dict) else parsed
        if isinstance(titles, list):
            for t in titles:
                if isinstance(t, str) and t.strip():
                    candidates.append(t.strip())
    except Exception:
        pass

    if not candidates:
        for line in raw.splitlines():
            line = line.strip().lstrip("-*•").strip()
            line = re.sub(r"^\d+[).]\s*", "", line)
            if line:
                candidates.append(line)
            if len(candidates) >= 3:
                break

    # Normalize, de-dupe.
    seen = set()
    out: List[str] = []
    for t in candidates:
        t = t.strip().strip('"').strip()
        # Enforce "short title" constraint defensively.
        words = t.split()
        if len(words) > 8:
            t = " ".join(words[:8])
        if not t:
            continue
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
        if len(out) >= 3:
            break
    return out


def _rel_to_library(path: Path) -> str:
    return str(path.resolve().relative_to(library_root()))


def maybe_embed_transcript(session_id: str, session_dir: Path, transcript_path: Path, settings: dict) -> Optional[Path]:
    """Embed a transcript if enabled; returns embedding file path or None."""
    if not settings.get("auto_embed"):
        return None
    emb = embed_text_file(str(transcript_path), session_key=session_id, output_dir=str(session_dir))
    if not emb:
        return None
    emb_path = Path(emb).resolve()
    meta = load_meta(session_dir)
    meta.setdefault("assets", {})
    meta["assets"]["embedding_json"] = emb_path.name
    save_meta(session_dir, meta)
    update_session_paths(session_id, embedding_path=_rel_to_library(emb_path), embedded=True)
    return emb_path


def maybe_summarize_transcript(session_id: str, session_dir: Path, transcript_path: Path, settings: dict) -> Optional[Path]:
    """Generate a summary if enabled; returns summary path or None."""
    if not settings.get("auto_summarize"):
        return None
    summary_path = (session_dir / "summary.txt").resolve()
    txt = transcript_path.read_text(encoding="utf-8", errors="ignore")
    summary = generate_summary(txt)
    summary_path.write_text(summary, encoding="utf-8")
    meta = load_meta(session_dir)
    meta.setdefault("assets", {})
    meta["assets"]["summary_txt"] = summary_path.name
    save_meta(session_dir, meta)
    update_session_paths(session_id, summary_path=_rel_to_library(summary_path))
    return summary_path


def maybe_suggest_title(session_id: str, session_dir: Path, transcript_path: Path, settings: dict) -> List[str]:
    """Generate title candidates if enabled; returns candidate list (possibly empty)."""
    if not settings.get("auto_title_suggest"):
        return []
    txt = transcript_path.read_text(encoding="utf-8", errors="ignore")
    meta = load_meta(session_dir)
    candidates = generate_title_candidates(
        txt,
        calendar=meta.get("calendar") or None,
        participants=meta.get("participants") or [],
    )
    meta.setdefault("suggestions", {})
    meta["suggestions"]["title_candidates"] = candidates
    save_meta(session_dir, meta)
    set_session_suggested_titles(session_id, candidates, selected=None)
    return candidates


def cosine(a, b):
    a = np.array(a)
    b = np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

def resolve_session_dir(session_id: str) -> Path:
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    session_dir_rel = sess.get("session_dir")
    if not session_dir_rel:
        raise HTTPException(status_code=404, detail="Session has no on-disk directory (legacy session)")
    root = library_root()
    abs_dir = (root / session_dir_rel).resolve()
    if abs_dir.exists():
        return abs_dir
    # Attempt a quick reconcile if the user moved things in Finder while the app was closed.
    reconcile_library()
    sess2 = get_session(session_id)
    if not sess2 or not sess2.get("session_dir"):
        raise HTTPException(status_code=404, detail="Session not found on disk")
    abs_dir = (root / sess2["session_dir"]).resolve()
    if not abs_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found on disk")
    return abs_dir


@app.on_event("startup")
async def _startup():
    ensure_dirs()
    global asr_pipeline, asr_device
    if asr_pipeline is None:
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

@app.get("/folders")
def folders():
    return list_folders()


@app.post("/folders")
def create_folder_endpoint(payload: dict):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    # Use a filesystem-safe directory name; keep it stable even if display name changes.
    dir_name = (payload.get("dir_name") or "").strip() or "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    if not dir_name:
        dir_name = "folder"
    ensure_folder_dir(dir_name)
    try:
        return create_folder(name=name, dir_name=dir_name, parent_id=payload.get("parent_id"))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Folder dir_name already exists")


@app.post("/folders/{folder_id}/rename")
def rename_folder_endpoint(folder_id: int, payload: dict):
    new_name = (payload.get("name") or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="name is required")
    current = next((f for f in list_folders() if f["id"] == folder_id), None)
    if not current:
        raise HTTPException(status_code=404, detail="Folder not found")
    if current.get("kind") != "normal":
        raise HTTPException(status_code=400, detail="System folders cannot be renamed")
    new_dir = (payload.get("dir_name") or "").strip() or "".join(ch if ch.isalnum() else "-" for ch in new_name.lower()).strip("-")
    if not new_dir:
        raise HTTPException(status_code=400, detail="dir_name is required")
    # Rename physical directory if it exists.
    src = (folders_root() / current["dir_name"]).resolve()
    dst = (folders_root() / new_dir).resolve()
    if src.exists() and src != dst:
        if dst.exists():
            raise HTTPException(status_code=409, detail="Target folder directory already exists")
        os.rename(src, dst)
    ensure_folder_dir(new_dir)
    rename_folder(folder_id, new_name, new_dir)
    return {"status": "ok"}


@app.delete("/folders/{folder_id}")
def delete_folder_endpoint(folder_id: int):
    current = next((f for f in list_folders() if f["id"] == folder_id), None)
    if not current:
        raise HTTPException(status_code=404, detail="Folder not found")
    if current.get("kind") != "normal":
        raise HTTPException(status_code=400, detail="System folders cannot be deleted")
    # Move the physical folder to Trash (non-destructive) if present.
    src = (folders_root() / current["dir_name"]).resolve()
    if src.exists():
        trash_parent = (trash_root() / "Folders").resolve()
        trash_parent.mkdir(parents=True, exist_ok=True)
        dst = trash_parent / src.name
        if dst.exists():
            dst = trash_parent / f"{src.name}__deleted_{int(time.time())}"
        shutil.move(str(src), str(dst))
    delete_folder(folder_id)
    return {"status": "ok"}

@app.get("/sessions")
def sessions(folder_id: Optional[int] = None):
    return list_sessions(folder_id=folder_id)


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    ensure_dirs()
    inbox = get_folder_by_dir("Inbox")
    if not inbox:
        raise HTTPException(status_code=500, detail="Inbox folder missing")
    session_id, session_dir, meta = create_session_dir(title=file.filename, tags="upload", kind="inbox")
    ext = Path(file.filename).suffix.lower() or ".webm"
    audio_name = f"audio{ext}"
    audio_path = (session_dir / audio_name).resolve()
    audio_path.write_bytes(await file.read())
    meta.setdefault("assets", {})
    meta["assets"]["audio"] = audio_name
    save_meta(session_dir, meta)
    upsert_session(
        session_id=session_id,
        timestamp=meta.get("created_at") or datetime.datetime.utcnow().isoformat(),
        title=meta.get("title") or file.filename,
        tags=meta.get("tags") or "upload",
        audio_path=_rel_to_library(audio_path),
        session_dir=_rel_to_library(session_dir),
        folder_id=inbox["id"],
        participants=meta.get("participants") or [],
        calendar=meta.get("calendar") or None,
        missing_on_disk=False,
    )
    return {"session_id": session_id}


@app.post("/sessions/{session_id}/transcribe")
def transcribe_session(session_id: str, payload: dict):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    assets = meta.get("assets") or {}
    audio_name = assets.get("audio")
    audio_path = resolve_asset_path(session_dir, audio_name)
    if not audio_path or not audio_path.exists():
        raise HTTPException(status_code=400, detail="Audio missing for session")
    settings = load_settings()
    vocab_prompt = " ".join(load_vocab()) or None
    transcript_tmp = transcribe_with_diarization(
        str(audio_path),
        prompt_name_mapping=False,
        language=(payload.get("language") or settings.get("language")),
        asr_model=settings.get("asr_model"),
        initial_prompt=vocab_prompt,
        pipeline=asr_pipeline,
        output_dir=str(session_dir),
    )
    transcript_path = Path(transcript_tmp).resolve()
    struct_path = transcript_path.with_suffix(".json")
    meta.setdefault("assets", {})
    meta["assets"]["transcript_txt"] = transcript_path.name
    meta["assets"]["transcript_json"] = struct_path.name if struct_path.exists() else None
    save_meta(session_dir, meta)
    update_session_paths(session_id, transcript_path=_rel_to_library(transcript_path), diarized=True)
    embedding_path = maybe_embed_transcript(session_id, session_dir, transcript_path, settings)
    summary_path = maybe_summarize_transcript(session_id, session_dir, transcript_path, settings)
    maybe_suggest_title(session_id, session_dir, transcript_path, settings)
    return {
        "session_id": session_id,
        "transcript_path": _rel_to_library(transcript_path),
        "embedding_path": _rel_to_library(embedding_path) if embedding_path else None,
        "summary_path": _rel_to_library(summary_path) if summary_path else None,
    }

@app.get("/sessions/{session_id}")
def get_session_endpoint(session_id: str):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


@app.get("/sessions/{session_id}/transcript")
def get_transcript(session_id: str):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    assets = meta.get("assets") or {}
    transcript_name = assets.get("transcript_txt")
    transcript_path = resolve_asset_path(session_dir, transcript_name)
    if not transcript_path or not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    txt = transcript_path.read_text(encoding="utf-8", errors="ignore")
    struct_name = assets.get("transcript_json")
    struct_path = resolve_asset_path(session_dir, struct_name) if struct_name else transcript_path.with_suffix(".json")
    structured = struct_path.read_text(encoding="utf-8") if struct_path and struct_path.exists() else None
    return {
        "session_id": session_id,
        "text": txt,
        "structured": structured,
        "title": meta.get("title") or "Untitled Session",
        "participants": meta.get("participants") or [],
        "calendar": meta.get("calendar") or None,
        "assets": assets,
    }


@app.get("/calendar/suggestions")
def calendar_suggestions(session_id: str, limit: int = 5):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    settings = load_settings()
    url = (settings.get("calendar_ics_url") or "").strip()
    if not url:
        return {"session_id": session_id, "suggestions": []}
    window = int(settings.get("calendar_match_window_minutes") or 45)
    cache_path = Path(LIBRARY_ROOT) / "calendar_cache.json"
    try:
        events = fetch_ics_events(url, cache_path=cache_path, max_age_seconds=600)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed fetching calendar feed: {exc}")
    suggestions = suggest_events(events=events, session_time_iso=sess.get("timestamp") or "", window_minutes=window, limit=limit)
    return {"session_id": session_id, "suggestions": suggestions}


@app.post("/sessions/{session_id}/calendar_link")
def calendar_link(session_id: str, payload: dict):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    event = payload.get("event") or payload
    if not isinstance(event, dict) or not event.get("uid"):
        raise HTTPException(status_code=400, detail="event.uid is required")
    calendar = {
        "uid": event.get("uid"),
        "summary": event.get("summary") or event.get("title") or "",
        "start": event.get("start"),
        "end": event.get("end"),
        "location": event.get("location"),
        "attendees": event.get("attendees") or [],
    }
    meta["calendar"] = calendar

    apply_participants = bool(payload.get("apply_participants", True))
    if apply_participants:
        participants = []
        for a in calendar.get("attendees") or []:
            if isinstance(a, dict):
                participants.append({"name": a.get("name"), "email": a.get("email")})
        meta["participants"] = participants

    save_meta(session_dir, meta)
    sess = get_session(session_id) or {}
    upsert_session(
        session_id=session_id,
        timestamp=sess.get("timestamp") or meta.get("created_at") or datetime.datetime.utcnow().isoformat(),
        title=meta.get("title") or sess.get("title") or "Untitled",
        tags=sess.get("tags") or meta.get("tags") or "",
        audio_path=sess.get("audio_path"),
        transcript_path=sess.get("transcript_path"),
        embedding_path=sess.get("embedding_path"),
        summary_path=sess.get("summary_path"),
        diarized=sess.get("diarized"),
        embedded=sess.get("embedded"),
        session_dir=sess.get("session_dir"),
        folder_id=sess.get("folder_id"),
        participants=meta.get("participants") or [],
        calendar=calendar,
        missing_on_disk=sess.get("missing_on_disk"),
    )
    return {"status": "ok", "calendar": calendar, "participants": meta.get("participants") or []}


@app.post("/sessions/{session_id}/suggest_title")
def suggest_title(session_id: str):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    assets = meta.get("assets") or {}
    transcript_name = assets.get("transcript_txt")
    transcript_path = resolve_asset_path(session_dir, transcript_name)
    if not transcript_path or not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    txt = transcript_path.read_text(encoding="utf-8", errors="ignore")
    candidates = generate_title_candidates(
        txt,
        calendar=meta.get("calendar") or None,
        participants=meta.get("participants") or [],
    )
    meta.setdefault("suggestions", {})
    meta["suggestions"]["title_candidates"] = candidates
    save_meta(session_dir, meta)
    set_session_suggested_titles(session_id, candidates, selected=None)
    return {"titles": candidates}


@app.post("/sessions/{session_id}/rename")
def rename_session(session_id: str, payload: dict):
    new_title = (payload.get("title") or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title is required")
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    meta["title"] = new_title
    save_meta(session_dir, meta)
    update_session_title_by_id(session_id, new_title)
    return {"status": "ok", "title": new_title}


@app.post("/sessions/{session_id}/speakers")
def update_speakers(session_id: str, payload: dict):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    assets = meta.get("assets") or {}
    transcript_name = assets.get("transcript_txt")
    transcript_path = resolve_asset_path(session_dir, transcript_name) if transcript_name else None
    if not transcript_path or not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    struct_name = assets.get("transcript_json")
    struct_path = resolve_asset_path(session_dir, struct_name) if struct_name else transcript_path.with_suffix(".json")
    if not struct_path or not struct_path.exists():
        raise HTTPException(status_code=400, detail="Structured transcript not found")

    updates = payload.get("updates", {})
    if not updates:
        return {"status": "no_changes"}

    data = json.loads(struct_path.read_text(encoding="utf-8"))
    changed = False
    for seg in data.get("segments", []):
        spk = seg.get("speaker")
        if spk in updates:
            seg["speaker"] = updates[spk]
            changed = True

    if changed:
        struct_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [f"[{seg.get('speaker', 'Unknown')}] {seg.get('text', '')}" for seg in data.get("segments", [])]
        transcript_path.write_text("\n".join(lines), encoding="utf-8")

    return {"status": "ok"}


@app.post("/sessions/{session_id}/embed")
def embed_session(session_id: str):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    assets = meta.get("assets") or {}
    transcript_name = assets.get("transcript_txt")
    transcript_path = resolve_asset_path(session_dir, transcript_name)
    if not transcript_path or not transcript_path.exists():
        raise HTTPException(status_code=400, detail="Transcript missing or not found")
    emb = embed_text_file(str(transcript_path), session_key=session_id, output_dir=str(session_dir))
    if not emb:
        raise HTTPException(status_code=500, detail="Embedding failed")
    emb_path = Path(emb).resolve()
    meta.setdefault("assets", {})
    meta["assets"]["embedding_json"] = emb_path.name
    save_meta(session_dir, meta)
    update_session_paths(session_id, embedding_path=_rel_to_library(emb_path), embedded=True)
    return {"embedding_path": _rel_to_library(emb_path)}


@app.post("/sessions/{session_id}/summarize")
def summarize_session(session_id: str, payload: dict):
    force = bool(payload.get("force", False))
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    assets = meta.get("assets") or {}
    transcript_name = assets.get("transcript_txt")
    transcript_path = resolve_asset_path(session_dir, transcript_name)
    if not transcript_path or not transcript_path.exists():
        raise HTTPException(status_code=404, detail="Transcript not found")
    summary_name = assets.get("summary_txt") or "summary.txt"
    summary_path = resolve_asset_path(session_dir, summary_name) or (session_dir / "summary.txt")
    if summary_path.exists() and not force:
        return {"summary": summary_path.read_text(encoding="utf-8")}
    txt = transcript_path.read_text(encoding="utf-8", errors="ignore")
    summary = generate_summary(txt)
    summary_path.write_text(summary, encoding="utf-8")
    meta.setdefault("assets", {})
    meta["assets"]["summary_txt"] = summary_path.name
    save_meta(session_dir, meta)
    update_session_paths(session_id, summary_path=_rel_to_library(summary_path))
    return {"summary": summary}


@app.get("/sessions/{session_id}/audio")
def get_audio(session_id: str, start: float = 0.0, end: float = 0.0):
    session_dir = resolve_session_dir(session_id)
    meta = load_meta(session_dir)
    audio_name = (meta.get("assets") or {}).get("audio")
    audio_path = resolve_asset_path(session_dir, audio_name)
    if not audio_path or not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    try:
        data, sr = librosa.load(str(audio_path), sr=None)
    except Exception as e:
        print(f"Error loading audio with librosa: {e}")
        data, sr = sf.read(str(audio_path), always_2d=False)
    start_frame = int(max(0, start) * sr)
    end_frame = int(len(data) if end <= 0 else min(len(data), end * sr))
    segment = data[start_frame:end_frame]
    buf = io.BytesIO()
    sf.write(buf, segment, sr, format="WAV")
    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")


@app.post("/sessions/{session_id}/move")
def move_session(session_id: str, payload: dict):
    folder_id = payload.get("folder_id")
    if folder_id is None:
        raise HTTPException(status_code=400, detail="folder_id is required")
    folders = list_folders()
    target = next((f for f in folders if f["id"] == int(folder_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="Folder not found")
    session_dir = resolve_session_dir(session_id)
    if target.get("dir_name") == "Inbox":
        dest_base = inbox_root()
    elif target.get("dir_name") == "Trash":
        dest_base = trash_root()
    else:
        dest_base = ensure_folder_dir(target["dir_name"])
    new_dir = move_session_dir(session_dir, dest_base)

    # Update DB paths from meta.
    meta = load_meta(new_dir)
    assets = meta.get("assets") or {}
    audio = resolve_asset_path(new_dir, assets.get("audio"))
    transcript = resolve_asset_path(new_dir, assets.get("transcript_txt"))
    embedding = resolve_asset_path(new_dir, assets.get("embedding_json"))
    summary = resolve_asset_path(new_dir, assets.get("summary_txt"))
    update_session_folder(session_id, int(folder_id), session_dir=_rel_to_library(new_dir))
    update_session_paths(
        session_id,
        audio_path=_rel_to_library(audio) if audio and audio.exists() else None,
        transcript_path=_rel_to_library(transcript) if transcript and transcript.exists() else None,
        embedding_path=_rel_to_library(embedding) if embedding and embedding.exists() else None,
        summary_path=_rel_to_library(summary) if summary and summary.exists() else None,
        missing_on_disk=False,
    )
    return {"status": "ok"}


@app.post("/library/reconcile")
def reconcile_endpoint():
    stats = reconcile_library()
    threshold = float(load_settings().get("folder_suggestion_threshold", 0.78))
    sugg = compute_folder_suggestions(threshold=threshold)
    return {"reconcile": stats, "folder_suggestions": sugg}


@app.get("/folder_suggestions")
def folder_suggestions():
    inbox = get_folder_by_dir("Inbox")
    if not inbox:
        return []
    sessions = list_sessions(folder_id=inbox["id"])
    return [s for s in sessions if s.get("suggested_folder_id")]


@app.post("/search")
def search(payload: dict):
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    threshold = float(payload.get("threshold", 0.75))
    settings = load_settings()
    q_emb = embed_query(prompt, model=settings.get("embed_model_query") or OLLAMA_EMBED_MODEL)
    results = []
    for hit in search_similar(q_emb, top_k=int(payload.get("top_k", 30))):
        if hit.get("similarity", 0.0) < threshold:
            continue
        sid = hit.get("session_path")
        sess = get_session(str(sid)) if sid else None
        results.append(
            {
                "kind": "chunk",
                "similarity": hit.get("similarity"),
                "session_id": sid,
                "title": (sess or {}).get("title") if sess else None,
                "start": hit.get("start", 0.0),
                "end": hit.get("end", 0.0),
                "snippet": hit.get("text", ""),
            }
        )
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return {"results": results}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    ensure_dirs()
    inbox = get_folder_by_dir("Inbox")
    if not inbox:
        await websocket.close(code=1011)
        return

    session_id, session_dir, meta = create_session_dir(title="Live Recording", tags="live", kind="inbox")
    audio_path = (session_dir / "audio.webm").resolve()
    meta.setdefault("assets", {})
    meta["assets"]["audio"] = audio_path.name
    save_meta(session_dir, meta)
    upsert_session(
        session_id=session_id,
        timestamp=meta.get("created_at") or datetime.datetime.utcnow().isoformat(),
        title=meta.get("title") or f"Live Recording {session_id[:8]}",
        tags=meta.get("tags") or "live",
        audio_path=_rel_to_library(audio_path),
        session_dir=_rel_to_library(session_dir),
        folder_id=inbox["id"],
        participants=meta.get("participants") or [],
        calendar=meta.get("calendar") or None,
        missing_on_disk=False,
    )

    # Let the client know which session this is.
    await websocket.send_text(json.dumps({"type": "session", "session_id": session_id}))

    try:
        with open(audio_path, "wb") as f:
            last_transcribe_time = time.time()
            while True:
                data = await websocket.receive_bytes()
                f.write(data)
                f.flush()

                now = time.time()
                if now - last_transcribe_time > 3:
                    last_transcribe_time = now

                    def run_transcription():
                        try:
                            duration = librosa.get_duration(path=str(audio_path))
                            offset = max(0, duration - 30)
                            audio, _sr = librosa.load(str(audio_path), sr=16000, offset=offset)
                            return asr_pipeline.transcribe(audio, batch_size=16)
                        except Exception as e:
                            print(f"Transcribe chunk failed: {e}")
                            return {"segments": []}

                    result = await asyncio.to_thread(run_transcription)
                    text = " ".join([seg.get("text", "") for seg in result.get("segments", [])]).strip()
                    await websocket.send_text(json.dumps({"type": "partial", "text": text}))
    except Exception as exc:
        # WebSocketDisconnect derives from Exception; treat as stop.
        print(f"Live recording stopped: {exc}")
    finally:
        # Trigger full pipeline after stop.
        try:
            settings = load_settings()
            vocab_prompt = " ".join(load_vocab()) or None

            def run_pipeline():
                transcript_tmp = transcribe_with_diarization(
                    str(audio_path),
                    prompt_name_mapping=False,
                    language=settings.get("language"),
                    asr_model=settings.get("asr_model"),
                    initial_prompt=vocab_prompt,
                    pipeline=asr_pipeline,
                    output_dir=str(session_dir),
                )
                transcript_path = Path(transcript_tmp).resolve()
                struct_path = transcript_path.with_suffix(".json")
                m = load_meta(session_dir)
                m.setdefault("assets", {})
                m["assets"]["transcript_txt"] = transcript_path.name
                m["assets"]["transcript_json"] = struct_path.name if struct_path.exists() else None
                save_meta(session_dir, m)
                update_session_paths(session_id, transcript_path=_rel_to_library(transcript_path), diarized=True)
                maybe_embed_transcript(session_id, session_dir, transcript_path, settings)
                maybe_summarize_transcript(session_id, session_dir, transcript_path, settings)
                maybe_suggest_title(session_id, session_dir, transcript_path, settings)

            await asyncio.to_thread(run_pipeline)
        except Exception as e:
            print(f"Error in post-processing: {e}")


frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
