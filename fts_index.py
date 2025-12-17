"""Lightweight SQLite FTS index for transcripts."""

import os
import sqlite3
from typing import Iterable, List, Optional

from config import DB_PATH


def init_fts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS transcript_fts USING fts5(
            session_path UNINDEXED,
            content,
            date,
            speakers,
            tags
        );
        """
    )
    conn.commit()
    conn.close()


def upsert_doc(session_path: str, content: str, date: str = "", speakers: str = "", tags: str = ""):
    if not session_path or not content:
        return
    init_fts()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM transcript_fts WHERE session_path = ?", (session_path,))
    c.execute(
        "INSERT INTO transcript_fts (session_path, content, date, speakers, tags) VALUES (?, ?, ?, ?, ?)",
        (session_path, content, date, speakers, tags),
    )
    conn.commit()
    conn.close()


def search_fts(query: str, limit: int = 50, date_filter: Optional[str] = None) -> List[dict]:
    init_fts()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if date_filter:
        cursor = c.execute(
            "SELECT session_path, snippet(transcript_fts, 1, '[', ']', '…', 10) as snip FROM transcript_fts WHERE content MATCH ? AND date = ? LIMIT ?",
            (query, date_filter, limit),
        )
    else:
        cursor = c.execute(
            "SELECT session_path, snippet(transcript_fts, 1, '[', ']', '…', 10) as snip FROM transcript_fts WHERE content MATCH ? LIMIT ?",
            (query, limit),
        )
    rows = [{"session_path": row[0], "snippet": row[1]} for row in cursor.fetchall()]
    conn.close()
    return rows
