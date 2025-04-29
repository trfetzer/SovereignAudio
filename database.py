import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            title TEXT,
            tags TEXT,
            audio_path TEXT,
            transcript_path TEXT,
            embedding_path TEXT,
            diarized BOOLEAN DEFAULT 0,
            embedded BOOLEAN DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def insert_session(timestamp, title, tags, audio_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (timestamp, title, tags, audio_path) VALUES (?, ?, ?, ?)",
        (timestamp, title, tags, audio_path)
    )
    conn.commit()
    conn.close()

def update_transcript(audio_path, transcript_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET transcript_path=?, diarized=1 WHERE audio_path=?",
        (transcript_path, audio_path)
    )
    conn.commit()
    conn.close()

def update_embedding(transcript_path, embedding_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE sessions SET embedding_path=?, embedded=1 WHERE transcript_path=?",
        (embedding_path, transcript_path)
    )
    conn.commit()
    conn.close()
