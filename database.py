import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import DB_PATH


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in c.fetchall()]

def init_db():
    _ensure_parent_dir(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            timestamp TEXT,
            title TEXT,
            tags TEXT,
            audio_path TEXT,
            transcript_path TEXT,
            embedding_path TEXT,
            summary_path TEXT,
            diarized BOOLEAN DEFAULT 0,
            embedded BOOLEAN DEFAULT 0,

            -- Physical library + reconciliation
            session_dir TEXT,
            folder_id INTEGER,
            participants_json TEXT,
            calendar_event_uid TEXT,
            calendar_title TEXT,
            calendar_start TEXT,
            calendar_end TEXT,
            suggested_titles_json TEXT,
            suggested_title TEXT,
            suggested_folder_id INTEGER,
            suggested_folder_score REAL,
            suggested_folder_rationale TEXT,
            missing_on_disk BOOLEAN DEFAULT 0,
            updated_at TEXT
        )
    """)
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_folder ON sessions(folder_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON sessions(timestamp)")

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dir_name TEXT NOT NULL,
            parent_id INTEGER,
            kind TEXT NOT NULL DEFAULT 'normal',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_dir_name ON folders(dir_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id)")

    conn.commit()
    _ensure_columns(conn)
    _ensure_system_folders(conn)
    conn.commit()
    conn.close()


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cols = set(_table_columns(conn, "sessions"))
    required = {
        "session_id": "TEXT",
        "summary_path": "TEXT",
        "session_dir": "TEXT",
        "folder_id": "INTEGER",
        "participants_json": "TEXT",
        "calendar_event_uid": "TEXT",
        "calendar_title": "TEXT",
        "calendar_start": "TEXT",
        "calendar_end": "TEXT",
        "suggested_titles_json": "TEXT",
        "suggested_title": "TEXT",
        "suggested_folder_id": "INTEGER",
        "suggested_folder_score": "REAL",
        "suggested_folder_rationale": "TEXT",
        "missing_on_disk": "BOOLEAN DEFAULT 0",
        "updated_at": "TEXT",
    }
    if not required.keys() - cols:
        return
    c = conn.cursor()
    for name, decl in required.items():
        if name in cols:
            continue
        c.execute(f"ALTER TABLE sessions ADD COLUMN {name} {decl}")


def _ensure_system_folders(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    now = _utc_now_iso()
    # dir_name is the on-disk directory name under LIBRARY_ROOT.
    system = [
        ("Inbox", "Inbox", "system"),
        ("Trash", "Trash", "system"),
    ]
    for name, dir_name, kind in system:
        c.execute("SELECT id FROM folders WHERE dir_name = ?", (dir_name,))
        if c.fetchone():
            continue
        c.execute(
            "INSERT INTO folders (name, dir_name, parent_id, kind, created_at, updated_at) VALUES (?, ?, NULL, ?, ?, ?)",
            (name, dir_name, kind, now, now),
        )


def list_folders() -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    rows = c.execute(
        "SELECT id, name, dir_name, parent_id, kind FROM folders ORDER BY kind DESC, name ASC"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "dir_name": r[2], "parent_id": r[3], "kind": r[4]}
        for r in rows
    ]


def get_folder_by_dir(dir_name: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    row = c.execute(
        "SELECT id, name, dir_name, parent_id, kind FROM folders WHERE dir_name = ?",
        (dir_name,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "name": row[1], "dir_name": row[2], "parent_id": row[3], "kind": row[4]}


def create_folder(name: str, dir_name: str, parent_id: Optional[int] = None) -> Dict[str, Any]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = _utc_now_iso()
    c.execute(
        "INSERT INTO folders (name, dir_name, parent_id, kind, created_at, updated_at) VALUES (?, ?, ?, 'normal', ?, ?)",
        (name, dir_name, parent_id, now, now),
    )
    folder_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"id": folder_id, "name": name, "dir_name": dir_name, "parent_id": parent_id, "kind": "normal"}


def rename_folder(folder_id: int, new_name: str, new_dir_name: str) -> None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE folders SET name = ?, dir_name = ?, updated_at = ? WHERE id = ?",
        (new_name, new_dir_name, _utc_now_iso(), folder_id),
    )
    conn.commit()
    conn.close()


def delete_folder(folder_id: int) -> None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM folders WHERE id = ? AND kind = 'normal'", (folder_id,))
    conn.commit()
    conn.close()


def upsert_session(
    *,
    session_id: str,
    timestamp: str,
    title: str,
    tags: str,
    audio_path: Optional[str] = None,
    transcript_path: Optional[str] = None,
    embedding_path: Optional[str] = None,
    summary_path: Optional[str] = None,
    diarized: Optional[bool] = None,
    embedded: Optional[bool] = None,
    session_dir: Optional[str] = None,
    folder_id: Optional[int] = None,
    participants: Optional[Any] = None,
    calendar: Optional[Dict[str, Any]] = None,
    missing_on_disk: Optional[bool] = None,
) -> None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    participants_json = json.dumps(participants or [], ensure_ascii=False)
    cal_uid = cal_title = cal_start = cal_end = None
    if calendar:
        cal_uid = calendar.get("uid")
        cal_title = calendar.get("summary") or calendar.get("title")
        cal_start = calendar.get("start")
        cal_end = calendar.get("end")

    c.execute("SELECT id FROM sessions WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    now = _utc_now_iso()
    if row:
        updates = {
            "timestamp": timestamp,
            "title": title,
            "tags": tags,
            "audio_path": audio_path,
            "transcript_path": transcript_path,
            "embedding_path": embedding_path,
            "summary_path": summary_path,
            "session_dir": session_dir,
            "folder_id": folder_id,
            "participants_json": participants_json,
            "calendar_event_uid": cal_uid,
            "calendar_title": cal_title,
            "calendar_start": cal_start,
            "calendar_end": cal_end,
            "updated_at": now,
        }
        if diarized is not None:
            updates["diarized"] = int(bool(diarized))
        if embedded is not None:
            updates["embedded"] = int(bool(embedded))
        if missing_on_disk is not None:
            updates["missing_on_disk"] = int(bool(missing_on_disk))
        assignments = ", ".join([f"{k} = ?" for k in updates.keys() if updates[k] is not None])
        values = [updates[k] for k in updates.keys() if updates[k] is not None]
        if assignments:
            c.execute(f"UPDATE sessions SET {assignments} WHERE session_id = ?", (*values, session_id))
    else:
        c.execute(
            """
            INSERT INTO sessions (
                session_id, timestamp, title, tags,
                audio_path, transcript_path, embedding_path, summary_path,
                diarized, embedded,
                session_dir, folder_id, participants_json,
                calendar_event_uid, calendar_title, calendar_start, calendar_end,
                missing_on_disk, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                timestamp,
                title,
                tags,
                audio_path,
                transcript_path,
                embedding_path,
                summary_path,
                int(bool(diarized)) if diarized is not None else 0,
                int(bool(embedded)) if embedded is not None else 0,
                session_dir,
                folder_id,
                participants_json,
                cal_uid,
                cal_title,
                cal_start,
                cal_end,
                int(bool(missing_on_disk)) if missing_on_disk is not None else 0,
                now,
            ),
        )
    conn.commit()
    conn.close()

def insert_session(timestamp, title, tags, audio_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Legacy helper: keep id-based sessions, but also fill session_id for newer codepaths if possible.
    c.execute("INSERT INTO sessions (session_id, timestamp, title, tags, audio_path, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
              (None, timestamp, title, tags, audio_path, _utc_now_iso()))
    conn.commit()
    conn.close()

def update_transcript(audio_path, transcript_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET transcript_path=?, diarized=1 WHERE audio_path=?",
        (transcript_path, audio_path)
    )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated

def update_embedding(transcript_path, embedding_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET embedding_path=?, embedded=1 WHERE transcript_path=?",
        (embedding_path, transcript_path)
    )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated

def update_session_title(transcript_path, new_title):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET title=? WHERE transcript_path=?",
        (new_title, transcript_path)
    )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated

def update_session_title_by_id(session_id: str, new_title: str) -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
        (new_title, _utc_now_iso(), session_id),
    )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated


def update_session_folder(session_id: str, folder_id: int, session_dir: Optional[str] = None) -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if session_dir is not None:
        c.execute(
            "UPDATE sessions SET folder_id = ?, session_dir = ?, updated_at = ? WHERE session_id = ?",
            (folder_id, session_dir, _utc_now_iso(), session_id),
        )
    else:
        c.execute(
            "UPDATE sessions SET folder_id = ?, updated_at = ? WHERE session_id = ?",
            (folder_id, _utc_now_iso(), session_id),
        )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated


def update_session_paths(
    session_id: str,
    *,
    audio_path: Optional[str] = None,
    transcript_path: Optional[str] = None,
    embedding_path: Optional[str] = None,
    summary_path: Optional[str] = None,
    diarized: Optional[bool] = None,
    embedded: Optional[bool] = None,
    missing_on_disk: Optional[bool] = None,
) -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    updates: Dict[str, Any] = {"updated_at": _utc_now_iso()}
    if audio_path is not None:
        updates["audio_path"] = audio_path
    if transcript_path is not None:
        updates["transcript_path"] = transcript_path
    if embedding_path is not None:
        updates["embedding_path"] = embedding_path
    if summary_path is not None:
        updates["summary_path"] = summary_path
    if diarized is not None:
        updates["diarized"] = int(bool(diarized))
    if embedded is not None:
        updates["embedded"] = int(bool(embedded))
    if missing_on_disk is not None:
        updates["missing_on_disk"] = int(bool(missing_on_disk))
    assignments = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values())
    c.execute(f"UPDATE sessions SET {assignments} WHERE session_id = ?", (*values, session_id))
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated


def set_session_suggested_folder(session_id: str, folder_id: Optional[int], score: Optional[float], rationale: str = "") -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET suggested_folder_id = ?, suggested_folder_score = ?, suggested_folder_rationale = ?, updated_at = ? WHERE session_id = ?",
        (folder_id, score, rationale, _utc_now_iso(), session_id),
    )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated


def set_session_suggested_titles(session_id: str, candidates: List[str], selected: Optional[str] = None) -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET suggested_titles_json = ?, suggested_title = ?, updated_at = ? WHERE session_id = ?",
        (json.dumps(candidates or [], ensure_ascii=False), selected, _utc_now_iso(), session_id),
    )
    updated = c.rowcount
    conn.commit()
    conn.close()
    return updated


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    row = c.execute(
        """
        SELECT session_id, timestamp, title, tags, folder_id, session_dir,
               audio_path, transcript_path, embedding_path, summary_path,
               participants_json, calendar_event_uid, calendar_title, calendar_start, calendar_end,
               diarized, embedded, missing_on_disk,
               suggested_titles_json, suggested_title,
               suggested_folder_id, suggested_folder_score, suggested_folder_rationale
        FROM sessions WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    participants = []
    try:
        participants = json.loads(row[10] or "[]")
    except Exception:
        participants = []
    suggested_titles = []
    try:
        suggested_titles = json.loads(row[18] or "[]")
    except Exception:
        suggested_titles = []
    return {
        "session_id": row[0],
        "timestamp": row[1],
        "title": row[2],
        "tags": row[3],
        "folder_id": row[4],
        "session_dir": row[5],
        "audio_path": row[6],
        "transcript_path": row[7],
        "embedding_path": row[8],
        "summary_path": row[9],
        "participants": participants,
        "calendar": {
            "uid": row[11],
            "summary": row[12],
            "start": row[13],
            "end": row[14],
        }
        if any([row[11], row[12], row[13], row[14]])
        else None,
        "diarized": bool(row[15]),
        "embedded": bool(row[16]),
        "missing_on_disk": bool(row[17]),
        "suggested_titles": suggested_titles,
        "suggested_title": row[19],
        "suggested_folder_id": row[20],
        "suggested_folder_score": row[21],
        "suggested_folder_rationale": row[22],
    }


def list_sessions(folder_id: Optional[int] = None) -> List[Dict[str, Any]]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if folder_id is None:
        rows = c.execute(
            """
            SELECT session_id, timestamp, title, tags, folder_id, session_dir,
                   audio_path, transcript_path, embedding_path, summary_path,
                   diarized, embedded, missing_on_disk,
                   suggested_folder_id, suggested_folder_score
            FROM sessions
            WHERE session_id IS NOT NULL
            ORDER BY timestamp DESC
            """
        ).fetchall()
    else:
        rows = c.execute(
            """
            SELECT session_id, timestamp, title, tags, folder_id, session_dir,
                   audio_path, transcript_path, embedding_path, summary_path,
                   diarized, embedded, missing_on_disk,
                   suggested_folder_id, suggested_folder_score
            FROM sessions
            WHERE session_id IS NOT NULL AND folder_id = ?
            ORDER BY timestamp DESC
            """,
            (folder_id,),
        ).fetchall()
    conn.close()
    return [
        {
            "session_id": r[0],
            "timestamp": r[1],
            "title": r[2],
            "tags": r[3],
            "folder_id": r[4],
            "session_dir": r[5],
            "audio_path": r[6],
            "transcript_path": r[7],
            "embedding_path": r[8],
            "summary_path": r[9],
            "diarized": bool(r[10]),
            "embedded": bool(r[11]),
            "missing_on_disk": bool(r[12]),
            "suggested_folder_id": r[13],
            "suggested_folder_score": r[14],
        }
        for r in rows
    ]

def get_session_by_transcript(transcript_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, title, timestamp FROM sessions WHERE transcript_path=?",
        (transcript_path,)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "title": row[1], "timestamp": row[2]}
    return None
