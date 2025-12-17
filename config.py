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

# --- Model + indexing defaults (local-first) ---
# WhisperX model + compute type; override to pick smaller/faster or larger models.
ASR_MODEL = "medium"
ASR_COMPUTE_TYPE = "float32"
# Default language for ASR; users can still run multilingual audio.
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ["en", "es", "fr", "ja"]

# Embedding models (kept separate so queries and documents can diverge).
EMBED_MODEL_DOC = "mxbai-embed-large:latest"
EMBED_MODEL_QUERY = "mxbai-embed-large:latest"

# Local LLMs for downstream summarisation/QA (placeholders; not yet wired to UI).
SUMMARY_MODEL_FAST = "llama3:latest"
SUMMARY_MODEL_DEEP = "llama3:latest"

# Vector index storage (per-chunk embeddings live here).
VECTOR_DB_PATH = "vector_index.db"

# Chunking heuristics for transcripts before embedding.
CHUNK_MAX_WORDS = 220
CHUNK_MIN_WORDS = 40
CHUNK_OVERLAP_SECONDS = 3.0
