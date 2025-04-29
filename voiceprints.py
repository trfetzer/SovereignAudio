import os
import json
from config import VOICEPRINTS_FILE

def load_voiceprints():
    if os.path.exists(VOICEPRINTS_FILE):
        with open(VOICEPRINTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_voiceprints(data):
    with open(VOICEPRINTS_FILE, 'w') as f:
        json.dump(data, f)

def add_voiceprint(name, embedding):
    vps = load_voiceprints()
    vps[f"voice_{len(vps)}"] = {"name": name, "embedding": embedding}
    save_voiceprints(vps)
