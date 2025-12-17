#!/usr/bin/env python
"""Rebuild local search indexes (FTS + optional embeddings)."""

import argparse
import os

from config import TRANSCRIPT_FOLDER
from fts_index import upsert_doc, init_fts
from embedder import embed_text_file


def iter_transcripts():
    for root, _, files in os.walk(TRANSCRIPT_FOLDER):
        for f in files:
            if f.endswith(".txt"):
                yield os.path.join(root, f)


def rebuild(also_embed: bool = False):
    init_fts()
    for path in iter_transcripts():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            print(f"[warn] Cannot read {path}: {exc}")
            continue
        rel = os.path.relpath(path, TRANSCRIPT_FOLDER)
        # Derive date from first folder level if present.
        parts = rel.split(os.sep)
        date_part = parts[0] if len(parts) > 1 else ""
        upsert_doc(rel, content, date=date_part)
        print(f"[fts] indexed {rel}")
        if also_embed:
            try:
                embed_text_file(path)
            except Exception as exc:
                print(f"[warn] embedding failed for {path}: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Rebuild local search indexes.")
    parser.add_argument("--embed", action="store_true", help="Re-embed transcripts into the vector index.")
    args = parser.parse_args()
    rebuild(also_embed=args.embed)


if __name__ == "__main__":
    main()
