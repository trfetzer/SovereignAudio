"""Deprecated voiceprints store (disabled).

SovereignAudio intentionally does NOT persist speaker profiles ("voiceprints")
across conversations. Speaker clustering happens in-memory per conversation
inside `diarizer.py`, and the only persisted speaker information is the per-file
speaker labels in the transcript JSON/TXT.

This module keeps a legacy API surface but is a no-op to prevent accidental
writes to disk.
"""


def load_voiceprints():
    return {}


def save_voiceprints(_data):
    return None


def add_voiceprint(_name, _embedding):
    return None
