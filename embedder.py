import json
import os
from typing import Dict, List, Optional

import requests

from config import (
    EMBEDDINGS_FOLDER,
    OLLAMA_URL,
    OLLAMA_EMBED_MODEL,
    EMBED_MODEL_DOC,
    EMBED_MODEL_QUERY,
    TRANSCRIPT_FOLDER,
)
import settings
from chunker import (
    chunk_plaintext,
    chunk_structured_transcript,
    derive_structured_path,
    load_structured_transcript,
)
from vector_store import upsert_chunk_embeddings
from fts_index import upsert_doc


def _embed_text(prompt: str, model: str) -> Optional[List[float]]:
    resp = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": model, "prompt": prompt})
    resp.raise_for_status()
    return resp.json().get("embedding")


def _prepare_chunks(text_file_path: str) -> Dict:
    """Return structured/chunks for the given transcript path plus full text."""
    structured_path = derive_structured_path(text_file_path)
    structured = load_structured_transcript(structured_path)
    full_text = ""
    if structured:
        chunks = chunk_structured_transcript(structured)
        # Reconstruct a plain text view for FTS.
        lines = []
        for seg in structured.get("segments", []):
            speaker = seg.get("speaker", "Unknown")
            text = seg.get("text", "")
            lines.append(f"[{speaker}] {text}")
        full_text = "\n".join(lines)
    else:
        with open(text_file_path, "r", encoding="utf-8") as f:
            plain = f.read()
        chunks = chunk_plaintext(plain)
        full_text = plain
    return {"structured_path": structured_path, "structured": structured, "chunks": chunks, "text": full_text}


def embed_text_file(text_file_path: str, *, session_key: Optional[str] = None, output_dir: Optional[str] = None):
    """Embed a transcript into chunks + aggregate embedding JSON.

    Returns path to the aggregate embedding JSON (legacy-compatible).
    """
    try:
        prep = _prepare_chunks(text_file_path)
        chunks = prep["chunks"]
        full_text = prep["text"]

        embedded_chunks = []
        doc_model = settings.get_embed_model_doc() or EMBED_MODEL_DOC or OLLAMA_EMBED_MODEL
        for ch in chunks:
            try:
                emb = _embed_text(ch["text"], doc_model)
            except Exception as exc:
                print(f"Embedding chunk failed: {exc}")
                continue
            if emb:
                ch_with_emb = dict(ch)
                ch_with_emb["embedding"] = emb
                embedded_chunks.append(ch_with_emb)

        # Persist chunk embeddings to the vector store for retrieval.
        session_ref = session_key
        if not session_ref:
            try:
                session_ref = os.path.relpath(text_file_path, TRANSCRIPT_FOLDER)
            except ValueError:
                session_ref = text_file_path
        upsert_chunk_embeddings(session_ref, embedded_chunks)
        # Update FTS index with full text.
        upsert_doc(
            session_ref,
            full_text,
            date=str(session_ref).split(os.sep)[0] if os.sep in str(session_ref) else "",
        )

        # Aggregate embedding (mean of chunks) for legacy consumers.
        agg_embedding = None
        if embedded_chunks:
            import numpy as np

            agg_embedding = np.mean([ch["embedding"] for ch in embedded_chunks], axis=0).tolist()
        else:
            # Fallback: embed entire document if chunking failed.
            with open(text_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            agg_embedding = _embed_text(content, doc_model)

        if not agg_embedding:
            return None

        base = os.path.splitext(os.path.basename(text_file_path))[0]
        out_dir = output_dir or EMBEDDINGS_FOLDER
        out = os.path.join(out_dir, base + "_embedding.json")
        os.makedirs(out_dir, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"embedding": agg_embedding, "chunk_count": len(embedded_chunks)}, f)
        return out
    except Exception as e:
        print(f"Embedding failed: {e}")
    return None
