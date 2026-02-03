"""Runtime settings with sane defaults from config.

Allows UI to override model/language choices without touching config.py.
"""

import json
import os
from typing import Optional

from config import (
    ASR_MODEL,
    DEFAULT_LANGUAGE,
    EMBED_MODEL_DOC,
    EMBED_MODEL_QUERY,
    LIBRARY_ROOT,
)


SETTINGS_FILE = os.path.join(LIBRARY_ROOT, "settings.json")

_state = {
    "asr_model": ASR_MODEL,
    "language": DEFAULT_LANGUAGE,
    "embed_model_doc": EMBED_MODEL_DOC,
    "embed_model_query": EMBED_MODEL_QUERY,
    "input_device": None,
    "silence_autostop": True,
    "silence_seconds": 8.0,
    "silence_threshold": 0.003,
}


def _load_from_disk():
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _state.update({k: v for k, v in data.items() if k in _state})
    except Exception as exc:
        print(f"[warn] Failed to load settings: {exc}")


def _save_to_disk():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_state, f, indent=2)
    except Exception as exc:
        print(f"[warn] Failed to save settings: {exc}")


def set_asr_model(name: str):
    if name:
        _state["asr_model"] = name.strip()
        _save_to_disk()


def get_asr_model() -> str:
    return _state.get("asr_model", ASR_MODEL)


def set_language(code: str):
    if code:
        _state["language"] = code.strip()
        _save_to_disk()


def get_language() -> str:
    return _state.get("language", DEFAULT_LANGUAGE)


def set_embed_model_doc(name: str):
    if name:
        _state["embed_model_doc"] = name.strip()
        _save_to_disk()


def get_embed_model_doc() -> str:
    return _state.get("embed_model_doc", EMBED_MODEL_DOC)


def set_embed_model_query(name: str):
    if name:
        _state["embed_model_query"] = name.strip()
        _save_to_disk()


def get_embed_model_query() -> str:
    return _state.get("embed_model_query", EMBED_MODEL_QUERY)


def set_input_device(device):
    _state["input_device"] = device
    _save_to_disk()


def get_input_device():
    return _state.get("input_device")


def set_silence_autostop(enabled: bool):
    _state["silence_autostop"] = bool(enabled)
    _save_to_disk()


def get_silence_autostop() -> bool:
    return bool(_state.get("silence_autostop", False))


def set_silence_seconds(value: float):
    try:
        _state["silence_seconds"] = float(value)
    except Exception:
        pass
    _save_to_disk()


def get_silence_seconds() -> float:
    return float(_state.get("silence_seconds", 0.0))


def set_silence_threshold(value: float):
    try:
        _state["silence_threshold"] = float(value)
    except Exception:
        pass
    _save_to_disk()


def get_silence_threshold() -> float:
    return float(_state.get("silence_threshold", 0.0))


# Load persisted settings at import.
_load_from_disk()
