import os

# --- Config ---
DB_PATH = "file_index.db"
TRANSCRIPT_FOLDER = "transcriptions"
RECORDINGS_FOLDER = "recordings"
EMBEDDINGS_FOLDER = "embeddings"
VOICEPRINTS_FILE = "voiceprints.json"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "mxbai-embed-large:latest"

# Redirect torch hub cache
TORCH_HUB_CACHE = os.path.abspath("pipeline")
