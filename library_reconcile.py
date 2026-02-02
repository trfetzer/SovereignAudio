import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from config import LIBRARY_ROOT
from database import (
    create_folder,
    get_folder_by_dir,
    get_session,
    init_db,
    list_folders,
    list_sessions,
    set_session_suggested_folder,
    upsert_session,
)
from library_store import SessionLocation, classify_session_dir, iter_session_dirs, load_meta, resolve_asset_path


def _rel_to_library(path: Path) -> str:
    root = Path(LIBRARY_ROOT).expanduser().resolve()
    return str(path.resolve().relative_to(root))


def _ensure_folder_for_location(loc: SessionLocation) -> Dict:
    if loc.kind == "inbox":
        folder = get_folder_by_dir("Inbox")
        if folder:
            return folder
        # init_db creates system folders; this is just a fallback.
        return create_folder(name="Inbox", dir_name="Inbox")
    if loc.kind == "trash":
        folder = get_folder_by_dir("Trash")
        if folder:
            return folder
        return create_folder(name="Trash", dir_name="Trash")
    if loc.kind == "folder":
        dir_name = loc.folder_dir or "Unknown"
        existing = get_folder_by_dir(dir_name)
        if existing:
            return existing
        # If user created a folder in Finder, adopt it.
        return create_folder(name=dir_name, dir_name=dir_name)
    # Unknown: default to Inbox
    folder = get_folder_by_dir("Inbox")
    if folder:
        return folder
    return create_folder(name="Inbox", dir_name="Inbox")


def reconcile_library() -> Dict[str, int]:
    """Scan the on-disk library and upsert the DB index.

    The on-disk `meta.json` is treated as the source of truth for session identity.
    """
    init_db()

    seen: Set[str] = set()
    created = 0
    updated = 0

    for session_dir in iter_session_dirs():
        try:
            meta = load_meta(session_dir)
        except Exception:
            continue
        session_id = meta.get("session_id")
        if not session_id:
            continue

        existed = get_session(session_id) is not None
        loc = classify_session_dir(session_dir)
        folder = _ensure_folder_for_location(loc)
        session_dir_rel = _rel_to_library(session_dir)

        assets = meta.get("assets") or {}
        audio = resolve_asset_path(session_dir, assets.get("audio"))
        transcript_txt = resolve_asset_path(session_dir, assets.get("transcript_txt"))
        embedding_json = resolve_asset_path(session_dir, assets.get("embedding_json"))
        summary_txt = resolve_asset_path(session_dir, assets.get("summary_txt"))

        audio_rel = _rel_to_library(audio) if audio and audio.exists() else None
        transcript_rel = _rel_to_library(transcript_txt) if transcript_txt and transcript_txt.exists() else None
        embedding_rel = _rel_to_library(embedding_json) if embedding_json and embedding_json.exists() else None
        summary_rel = _rel_to_library(summary_txt) if summary_txt and summary_txt.exists() else None

        # Upsert session row.
        upsert_session(
            session_id=session_id,
            timestamp=meta.get("created_at") or "",
            title=meta.get("title") or "Untitled",
            tags=meta.get("tags") or "",
            audio_path=audio_rel,
            transcript_path=transcript_rel,
            embedding_path=embedding_rel,
            summary_path=summary_rel,
            diarized=bool(transcript_rel),
            embedded=bool(embedding_rel),
            session_dir=session_dir_rel,
            folder_id=folder.get("id"),
            participants=meta.get("participants") or [],
            calendar=meta.get("calendar") or None,
            missing_on_disk=False,
        )
        if existed:
            updated += 1
        else:
            created += 1
        seen.add(session_id)

    # Mark DB entries missing on disk.
    for sess in list_sessions():
        sid = sess.get("session_id")
        if not sid:
            continue
        if sid not in seen:
            upsert_session(
                session_id=sid,
                timestamp=sess.get("timestamp") or "",
                title=sess.get("title") or "Untitled",
                tags=sess.get("tags") or "",
                audio_path=sess.get("audio_path"),
                transcript_path=sess.get("transcript_path"),
                embedding_path=sess.get("embedding_path"),
                summary_path=sess.get("summary_path"),
                diarized=sess.get("diarized"),
                embedded=sess.get("embedded"),
                session_dir=sess.get("session_dir"),
                folder_id=sess.get("folder_id"),
                missing_on_disk=True,
            )

    return {"sessions_seen": len(seen), "created": created, "updated": updated}


def _load_embedding(path: str) -> Optional[np.ndarray]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        emb = data.get("embedding")
        if not emb:
            return None
        return np.asarray(emb, dtype=np.float32)
    except Exception:
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compute_folder_suggestions(threshold: float = 0.78) -> Dict[str, int]:
    """Suggest folders for inbox sessions based on embedding similarity to folder centroids."""
    init_db()
    folders = list_folders()
    folder_centroids: Dict[int, np.ndarray] = {}
    folder_counts: Dict[int, int] = {}

    # Build centroids for non-system folders.
    for f in folders:
        if f.get("kind") != "normal":
            continue
        fid = f["id"]
        vectors: List[np.ndarray] = []
        for sess in list_sessions(folder_id=fid):
            emb_path = sess.get("embedding_path")
            if not emb_path:
                continue
            abs_path = str(Path(LIBRARY_ROOT).expanduser().resolve() / emb_path) if not os.path.isabs(emb_path) else emb_path
            vec = _load_embedding(abs_path)
            if vec is not None:
                vectors.append(vec)
        if vectors:
            folder_centroids[fid] = np.mean(vectors, axis=0)
            folder_counts[fid] = len(vectors)

    inbox = get_folder_by_dir("Inbox")
    if not inbox:
        return {"suggested": 0, "skipped": 0}

    suggested = 0
    skipped = 0
    for sess in list_sessions(folder_id=inbox["id"]):
        emb_path = sess.get("embedding_path")
        if not emb_path:
            skipped += 1
            continue
        abs_path = str(Path(LIBRARY_ROOT).expanduser().resolve() / emb_path) if not os.path.isabs(emb_path) else emb_path
        vec = _load_embedding(abs_path)
        if vec is None:
            skipped += 1
            continue
        best_fid = None
        best_score = 0.0
        for fid, centroid in folder_centroids.items():
            score = _cosine(vec, centroid)
            if score > best_score:
                best_score = score
                best_fid = fid
        if best_fid is not None and best_score >= threshold:
            set_session_suggested_folder(
                sess["session_id"],
                best_fid,
                best_score,
                rationale=f"cosine≈{best_score:.3f} vs folder centroid",
            )
            suggested += 1
        else:
            set_session_suggested_folder(sess["session_id"], None, None, rationale="")
            skipped += 1

    return {"suggested": suggested, "skipped": skipped}
