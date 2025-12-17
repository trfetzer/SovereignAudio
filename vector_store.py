"""Lightweight on-disk vector store using SQLite BLOBs.

Stores per-chunk embeddings along with metadata so we can search locally
without external services or extra dependencies.
"""

import os
import sqlite3
from typing import Dict, Iterable, List, Optional

import numpy as np

from config import VECTOR_DB_PATH


def init_vector_db():
    os.makedirs(os.path.dirname(VECTOR_DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(VECTOR_DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_path TEXT,
            chunk_id TEXT,
            start REAL,
            end REAL,
            speakers TEXT,
            text TEXT,
            embedding BLOB
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(session_path)")
    conn.commit()
    conn.close()


def _to_blob(vec: Iterable[float]) -> bytes:
    arr = np.asarray(list(vec), dtype=np.float32)
    return arr.tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def upsert_chunk_embeddings(session_path: str, chunks: List[Dict]):
    """Replace embeddings for a given session_path with the supplied chunks."""
    if not chunks:
        return
    init_vector_db()
    conn = sqlite3.connect(VECTOR_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chunks WHERE session_path = ?", (session_path,))
    rows = [
        (
            session_path,
            ch.get("chunk_id"),
            float(ch.get("start", 0.0)),
            float(ch.get("end", 0.0)),
            ",".join(ch.get("speakers", [])),
            ch.get("text", ""),
            _to_blob(ch["embedding"]),
        )
        for ch in chunks
        if ch.get("embedding") is not None
    ]
    c.executemany(
        """
        INSERT INTO chunks (session_path, chunk_id, start, end, speakers, text, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def iter_chunks(session_filter: Optional[str] = None) -> Iterable[Dict]:
    init_vector_db()
    conn = sqlite3.connect(VECTOR_DB_PATH)
    c = conn.cursor()
    if session_filter:
        cursor = c.execute(
            "SELECT session_path, chunk_id, start, end, speakers, text, embedding FROM chunks WHERE session_path = ?",
            (session_filter,),
        )
    else:
        cursor = c.execute("SELECT session_path, chunk_id, start, end, speakers, text, embedding FROM chunks")
    for row in cursor:
        yield {
            "session_path": row[0],
            "chunk_id": row[1],
            "start": row[2],
            "end": row[3],
            "speakers": row[4].split(",") if row[4] else [],
            "text": row[5],
            "embedding": _from_blob(row[6]),
        }
    conn.close()


def search_similar(query_embedding: List[float], top_k: int = 30, session_filter: Optional[str] = None) -> List[Dict]:
    """Return top-k most similar chunks."""
    query = np.asarray(query_embedding, dtype=np.float32)
    if query.size == 0:
        return []
    results: List[Dict] = []
    for ch in iter_chunks(session_filter):
        emb = ch["embedding"]
        denom = (np.linalg.norm(query) * np.linalg.norm(emb))
        if denom == 0:
            continue
        sim = float(np.dot(query, emb) / denom)
        results.append(
            {
                "similarity": sim,
                "session_path": ch["session_path"],
                "chunk_id": ch["chunk_id"],
                "start": ch["start"],
                "end": ch["end"],
                "speakers": ch.get("speakers", []),
                "text": ch.get("text", ""),
            }
        )
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]
