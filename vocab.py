import json
import os

VOCAB_FILE = "vocab.json"


def load_vocab():
    if os.path.exists(VOCAB_FILE):
        try:
            with open(VOCAB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"[warn] Failed to load vocab: {exc}")
    return []


def save_vocab(words):
    try:
        with open(VOCAB_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, indent=2)
    except Exception as exc:
        print(f"[warn] Failed to save vocab: {exc}")


def vocab_prompt():
    words = load_vocab()
    if not words:
        return None
    return " ".join(words)
