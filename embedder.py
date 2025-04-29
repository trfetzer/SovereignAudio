import os
import json
import requests
from config import EMBEDDINGS_FOLDER, OLLAMA_URL, OLLAMA_EMBED_MODEL

def embed_text_file(text_file_path):
    try:
        with open(text_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": content}
        )
        resp.raise_for_status()
        emb = resp.json().get("embedding")
        if emb:
            base = os.path.splitext(os.path.basename(text_file_path))[0]
            out = os.path.join(EMBEDDINGS_FOLDER, base + ".json")
            with open(out, 'w') as f:
                json.dump({"embedding": emb}, f)
            return out
    except Exception as e:
        print(f"Embedding failed: {e}")
    return None
