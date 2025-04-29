import os
from config import RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER

def list_recordings():
    recs = []
    for root, _, files in os.walk(RECORDINGS_FOLDER):
        for f in files:
            if f.endswith('.wav'):
                recs.append(os.path.relpath(os.path.join(root, f), RECORDINGS_FOLDER))
    return sorted(recs)

def list_transcripts():
    trs = []
    for root, _, files in os.walk(TRANSCRIPT_FOLDER):
        for f in files:
            if f.endswith('_diarized.txt'):
                trs.append(os.path.relpath(os.path.join(root, f), TRANSCRIPT_FOLDER))
    return sorted(trs)

def list_embeddings():
    ems = []
    for root, _, files in os.walk(EMBEDDINGS_FOLDER):
        for f in files:
            if f.endswith('.json'):
                ems.append(os.path.relpath(os.path.join(root, f), EMBEDDINGS_FOLDER))
    return sorted(ems)
