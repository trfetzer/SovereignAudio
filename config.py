import os

# --- Config ---
LIBRARY_ROOT = os.environ.get("SOV_AUDIO_LIBRARY_ROOT") or os.path.abspath("library")
LIBRARY_INBOX_DIRNAME = "Inbox"
LIBRARY_FOLDERS_DIRNAME = "Folders"
LIBRARY_TRASH_DIRNAME = "Trash"

LIBRARY_INBOX = os.path.join(LIBRARY_ROOT, LIBRARY_INBOX_DIRNAME)
LIBRARY_FOLDERS = os.path.join(LIBRARY_ROOT, LIBRARY_FOLDERS_DIRNAME)
LIBRARY_TRASH = os.path.join(LIBRARY_ROOT, LIBRARY_TRASH_DIRNAME)

DB_PATH = os.environ.get("SOV_AUDIO_DB_PATH") or os.path.join(LIBRARY_ROOT, "file_index.db")

# Legacy folders (kept for compatibility with older scripts/pipelines).
TRANSCRIPT_FOLDER = os.environ.get("SOV_AUDIO_TRANSCRIPT_FOLDER") or os.path.join(LIBRARY_ROOT, "transcriptions")
RECORDINGS_FOLDER = os.environ.get("SOV_AUDIO_RECORDINGS_FOLDER") or os.path.join(LIBRARY_ROOT, "recordings")
EMBEDDINGS_FOLDER = os.environ.get("SOV_AUDIO_EMBEDDINGS_FOLDER") or os.path.join(LIBRARY_ROOT, "embeddings")

VOICEPRINTS_FILE = os.environ.get("SOV_AUDIO_VOICEPRINTS_FILE") or os.path.join(LIBRARY_ROOT, "voiceprints.json")
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
VECTOR_DB_PATH = os.environ.get("SOV_AUDIO_VECTOR_DB_PATH") or os.path.join(LIBRARY_ROOT, "vector_index.db")

# Chunking heuristics for transcripts before embedding.
CHUNK_MAX_WORDS = 220
CHUNK_MIN_WORDS = 40
CHUNK_OVERLAP_SECONDS = 3.0
