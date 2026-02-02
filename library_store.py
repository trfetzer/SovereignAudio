import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from config import LIBRARY_FOLDERS, LIBRARY_INBOX, LIBRARY_ROOT, LIBRARY_TRASH


META_FILENAME = "meta.json"
META_SCHEMA_VERSION = 1


def library_root() -> Path:
    return Path(LIBRARY_ROOT).expanduser().resolve()


def inbox_root() -> Path:
    return Path(LIBRARY_INBOX).expanduser().resolve()


def folders_root() -> Path:
    return Path(LIBRARY_FOLDERS).expanduser().resolve()


def trash_root() -> Path:
    return Path(LIBRARY_TRASH).expanduser().resolve()


def ensure_library_dirs() -> None:
    inbox_root().mkdir(parents=True, exist_ok=True)
    folders_root().mkdir(parents=True, exist_ok=True)
    trash_root().mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_slug(value: str, max_len: int = 64) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        value = "untitled"
    return value[:max_len]


def session_dir_name(session_id: str, created_at_iso: str, title: str = "") -> str:
    # Keep directory names stable and collision-resistant.
    # Include timestamp for sorting, plus a short title hint, plus the UUID.
    stamp = created_at_iso.replace(":", "-")
    hint = _safe_slug(title, max_len=32)
    return f"{stamp}__{hint}__{session_id}"


def meta_path(session_dir: Path) -> Path:
    return session_dir / META_FILENAME


def load_meta(session_dir: Path) -> Dict[str, Any]:
    path = meta_path(session_dir)
    return json.loads(path.read_text(encoding="utf-8"))


def save_meta(session_dir: Path, meta: Dict[str, Any]) -> None:
    path = meta_path(session_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def new_session_meta(
    session_id: str,
    created_at: str,
    title: str,
    tags: str = "",
    participants: Optional[list] = None,
    calendar: Optional[dict] = None,
    assets: Optional[dict] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": META_SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": created_at,
        "title": title,
        "tags": tags,
        "participants": participants or [],
        "calendar": calendar or None,
        "assets": assets
        or {
            "audio": None,
            "transcript_txt": None,
            "transcript_json": None,
            "embedding_json": None,
            "summary_txt": None,
        },
        "suggestions": {
            "title_candidates": [],
            "folder": None,
        },
    }


@dataclass(frozen=True)
class SessionLocation:
    kind: str  # "inbox" | "trash" | "folder" | "unknown"
    folder_dir: Optional[str] = None  # only for kind == "folder"


def classify_session_dir(session_dir: Path) -> SessionLocation:
    root = library_root()
    try:
        rel = session_dir.resolve().relative_to(root)
    except ValueError:
        return SessionLocation(kind="unknown", folder_dir=None)

    parts = rel.parts
    if not parts:
        return SessionLocation(kind="unknown", folder_dir=None)
    if parts[0] == inbox_root().name:
        return SessionLocation(kind="inbox", folder_dir=None)
    if parts[0] == trash_root().name:
        return SessionLocation(kind="trash", folder_dir=None)
    if parts[0] == folders_root().name and len(parts) >= 2:
        return SessionLocation(kind="folder", folder_dir=parts[1])
    return SessionLocation(kind="unknown", folder_dir=None)


def iter_session_dirs() -> Iterable[Path]:
    root = library_root()
    if not root.exists():
        return []
    # Only scan managed roots to avoid walking the entire working tree if LIBRARY_ROOT is mis-set.
    for base in [inbox_root(), folders_root(), trash_root()]:
        if not base.exists():
            continue
        for meta in base.rglob(META_FILENAME):
            yield meta.parent


def create_session_dir(title: str, tags: str = "", kind: str = "inbox") -> Tuple[str, Path, Dict[str, Any]]:
    ensure_library_dirs()
    session_id = uuid.uuid4().hex
    created_at = utc_now_iso()
    dirname = session_dir_name(session_id, created_at, title=title)
    if kind == "trash":
        base = trash_root()
    else:
        base = inbox_root()
    session_dir = (base / dirname).resolve()
    session_dir.mkdir(parents=True, exist_ok=False)
    meta = new_session_meta(session_id=session_id, created_at=created_at, title=title, tags=tags)
    save_meta(session_dir, meta)
    return session_id, session_dir, meta


def ensure_folder_dir(folder_dir: str) -> Path:
    ensure_library_dirs()
    folder_path = (folders_root() / folder_dir).resolve()
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def move_session_dir(session_dir: Path, dest_base: Path) -> Path:
    dest_base.mkdir(parents=True, exist_ok=True)
    target = dest_base / session_dir.name
    if target.exists():
        raise FileExistsError(f"Target already exists: {target}")
    try:
        return Path(shutil.move(str(session_dir), str(target))).resolve()
    except Exception:
        # shutil.move may partially move on errors; don't attempt aggressive cleanup here.
        raise


def resolve_asset_path(session_dir: Path, rel_name: Optional[str]) -> Optional[Path]:
    if not rel_name:
        return None
    return (session_dir / rel_name).resolve()


def write_audio_bytes(session_dir: Path, filename: str, data: bytes) -> Path:
    path = (session_dir / filename).resolve()
    path.write_bytes(data)
    return path

