#!/usr/bin/env python
"""Batch diarization/transcription for WAV files inside a folder."""

import argparse
import os
from pathlib import Path
from typing import Iterable

from config import RECORDINGS_FOLDER, TRANSCRIPT_FOLDER
from database import init_db, update_transcript
from diarizer import transcribe_with_diarization


PROJECT_ROOT = Path(__file__).resolve().parent
TRANSCRIPTS_ROOT = (PROJECT_ROOT / TRANSCRIPT_FOLDER).resolve()
RECORDINGS_ROOT = (PROJECT_ROOT / RECORDINGS_FOLDER).resolve()


def iter_wav_files(base: Path, recursive: bool) -> Iterable[Path]:
    """Yield WAV files from base directory."""
    iterator = base.rglob("*") if recursive else base.glob("*")
    for item in iterator:
        if item.is_file() and item.suffix.lower() == ".wav":
            yield item.resolve()


def ensure_database():
    """Make sure the sessions table exists before we update rows."""
    init_db()


def update_session(audio_path: Path, transcript_path: Path) -> bool:
    """Attempt to update the sessions table for the given audio/transcript pair."""
    candidates = {
        str(audio_path),
        os.path.relpath(audio_path, PROJECT_ROOT),
    }
    try:
        rel_to_recordings = audio_path.relative_to(RECORDINGS_ROOT)
        candidates.add(str(Path(RECORDINGS_FOLDER) / rel_to_recordings))
    except ValueError:
        pass

    rel_transcript = os.path.relpath(transcript_path, PROJECT_ROOT)
    for candidate in candidates:
        if update_transcript(candidate, rel_transcript):
            return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Create diarized transcripts for WAV files inside a folder."
    )
    parser.add_argument(
        "input_dir",
        help="Folder containing WAV files to process.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process WAV files in subdirectories recursively.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recreate transcripts even if they already exist.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        parser.error(f"Input directory not found: {input_dir}")

    ensure_database()
    TRANSCRIPTS_ROOT.mkdir(parents=True, exist_ok=True)

    wav_files = sorted(iter_wav_files(input_dir, args.recursive))
    if not wav_files:
        print(f"No WAV files found in {input_dir}")
        return

    print(f"Found {len(wav_files)} WAV file(s) under {input_dir}")
    for wav_path in wav_files:
        relative = wav_path.relative_to(input_dir)
        target_dir = TRANSCRIPTS_ROOT / relative.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / f"{wav_path.stem}.txt"
        final_path_abs = final_path.resolve()

        if final_path.exists() and not args.overwrite:
            print(f"[skip] {wav_path} -> transcript already exists")
            continue

        print(f"[transcribe] {wav_path}")
        try:
            transcript_tmp = transcribe_with_diarization(
                str(wav_path),
            )
        except Exception as exc:
            print(f"[error] Failed to transcribe {wav_path}: {exc}")
            continue

        if not transcript_tmp:
            print(f"[warn] Diarization did not produce a transcript for {wav_path}")
            continue

        temp_path = (PROJECT_ROOT / transcript_tmp).resolve()
        final_path_abs.parent.mkdir(parents=True, exist_ok=True)
        if temp_path != final_path_abs:
            if final_path_abs.exists():
                final_path_abs.unlink()
            os.replace(str(temp_path), str(final_path_abs))
        # Move structured JSON alongside the transcript if present.
        temp_json = temp_path.with_suffix(".json")
        final_json = final_path_abs.with_suffix(".json")
        if temp_json.exists():
            final_json.parent.mkdir(parents=True, exist_ok=True)
            if final_json.exists():
                final_json.unlink()
            os.replace(str(temp_json), str(final_json))

        db_updated = update_session(wav_path, final_path_abs)
        status = "updated DB" if db_updated else "no DB entry"
        print(f"[ok] Saved transcript to {final_path_abs} ({status})")


if __name__ == "__main__":
    main()
