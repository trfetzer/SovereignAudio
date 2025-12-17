"""Lightweight transcript chunking helpers for local embedding.

The goal is to create time-aware chunks (with speaker info) so we can
index and retrieve meaningful slices of a conversation.
"""

import json
import os
from typing import Dict, List, Optional

from config import CHUNK_MAX_WORDS, CHUNK_MIN_WORDS, CHUNK_OVERLAP_SECONDS


def derive_structured_path(text_path: str) -> str:
    """Return the expected JSON path for a diarized transcript."""
    base, _ = os.path.splitext(text_path)
    return base + ".json"


def load_structured_transcript(path: str) -> Optional[Dict]:
    """Load a structured transcript JSON if it exists."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _segment_words_with_fallback(seg: Dict, default_start: float, default_end: float) -> List[Dict]:
    """Return word-level entries for a segment, synthesising timestamps if missing."""
    words = []
    raw_words = seg.get("words")
    speaker = seg.get("speaker", "Unknown")
    if raw_words:
        for w in raw_words:
            words.append(
                {
                    "word": w.get("word", "").strip(),
                    "start": float(w.get("start", default_start)),
                    "end": float(w.get("end", default_end)),
                    "speaker": speaker,
                }
            )
    else:
        # Fallback: split text evenly across the segment window.
        tokens = seg.get("text", "").split()
        if not tokens:
            return []
        duration = max(0.001, float(default_end - default_start))
        step = duration / max(1, len(tokens))
        for idx, tok in enumerate(tokens):
            start = default_start + idx * step
            end = min(default_end, start + step)
            words.append({"word": tok, "start": start, "end": end, "speaker": speaker})
    return words


def flatten_words(segments: List[Dict]) -> List[Dict]:
    """Flatten segment-level data into a list of word entries with timestamps."""
    words: List[Dict] = []
    for seg in segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start))
        words.extend(_segment_words_with_fallback(seg, start, end))

    # Ensure monotonically increasing timestamps to avoid pathological overlaps.
    last_end = 0.0
    for w in words:
        if w["start"] < last_end:
            delta = last_end - w["start"]
            w["start"] += delta
            w["end"] += delta
        last_end = max(last_end, w["end"])
    return words


def chunk_words(
    words: List[Dict],
    max_words: int = CHUNK_MAX_WORDS,
    min_words: int = CHUNK_MIN_WORDS,
    overlap_seconds: float = CHUNK_OVERLAP_SECONDS,
) -> List[Dict]:
    """Chunk a word list into overlapping windows.

    Each chunk carries start/end time, text, and speaker set to preserve context.
    """
    chunks: List[Dict] = []
    if not words:
        return chunks

    start_idx = 0
    while start_idx < len(words):
        end_idx = start_idx
        # Grow until we hit max_words.
        while end_idx < len(words) and (end_idx - start_idx) < max_words:
            end_idx += 1

        # Enforce a minimum size if possible.
        if (end_idx - start_idx) < min_words and end_idx < len(words):
            deficit = min_words - (end_idx - start_idx)
            end_idx = min(len(words), end_idx + deficit)

        chunk_slice = words[start_idx:end_idx]
        if not chunk_slice:
            break

        chunk_start = chunk_slice[0]["start"]
        chunk_end = chunk_slice[-1]["end"]
        text = " ".join(w["word"] for w in chunk_slice).strip()
        speakers = sorted({w.get("speaker", "Unknown") for w in chunk_slice})

        chunks.append(
            {
                "chunk_id": f"chunk_{len(chunks):04d}",
                "start": float(chunk_start),
                "end": float(chunk_end),
                "speakers": speakers,
                "text": text,
            }
        )

        # Move start_idx forward with overlap.
        if overlap_seconds > 0 and end_idx < len(words):
            overlap_start_time = chunk_end - overlap_seconds
            # Step back until we include the overlap window.
            while end_idx > start_idx and words[end_idx - 1]["start"] >= overlap_start_time:
                end_idx -= 1
        start_idx = end_idx

    return chunks


def chunk_structured_transcript(structured: Dict) -> List[Dict]:
    """Chunk a structured transcript dictionary."""
    segments = structured.get("segments", [])
    words = flatten_words(segments)
    return chunk_words(words)


def chunk_plaintext(text: str) -> List[Dict]:
    """Fallback chunking when no structured transcript is available."""
    tokens = text.split()
    chunks: List[Dict] = []
    if not tokens:
        return chunks
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + CHUNK_MAX_WORDS)
        if (end - start) < CHUNK_MIN_WORDS and end < len(tokens):
            end = min(len(tokens), start + CHUNK_MIN_WORDS)
        span = tokens[start:end]
        chunks.append(
            {
                "chunk_id": f"chunk_{len(chunks):04d}",
                "start": 0.0,
                "end": 0.0,
                "speakers": [],
                "text": " ".join(span),
            }
        )
        # Overlap by a small percentage when synthetic timestamps are absent.
        overlap = max(0, int(CHUNK_MIN_WORDS * 0.2))
        start = end - overlap
    return chunks
