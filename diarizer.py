import os
import ssl
from pathlib import Path

import certifi
import numpy as np
import librosa
import torch
import whisperx
from resemblyzer import VoiceEncoder, preprocess_wav

from config import (
    TRANSCRIPT_FOLDER,
    ASR_MODEL,
    ASR_COMPUTE_TYPE,
    DEFAULT_LANGUAGE,
)


NLTK_DATA_DIR = Path(__file__).resolve().parent / "nltk_data"
NLTK_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NLTK_DATA", str(NLTK_DATA_DIR))
os.environ.setdefault("SSL_CERT_FILE", certifi.where())


encoder = VoiceEncoder()


def ensure_nltk_tokenizers():
    try:
        import nltk
        from nltk.data import find
    except ImportError:
        return

    data_path = str(NLTK_DATA_DIR)
    if data_path not in nltk.data.path:
        nltk.data.path.insert(0, data_path)

    required = [
        ("tokenizers/punkt/english.pickle", "punkt"),
        ("tokenizers/punkt_tab/english/", "punkt_tab"),
    ]

    missing = []
    for target, package in required:
        try:
            find(target)
        except LookupError:
            missing.append(package)

    if not missing:
        return

    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

    for package in missing:
        try:
            success = nltk.download(package, download_dir=data_path, quiet=True)
            if not success:
                print(f"[warn] NLTK reported failure fetching '{package}'.")
        except Exception as exc:
            print(f"[warn] Unable to fetch NLTK resource '{package}'. Some diarization steps may fail: {exc}")


def load_pipeline(language=None, asr_model=None):
    ensure_nltk_tokenizers()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    lang = language or DEFAULT_LANGUAGE
    model_name = asr_model or ASR_MODEL
    model = whisperx.load_model(model_name, device, language=lang, compute_type=ASR_COMPUTE_TYPE)
    return model, device

def transcribe_with_diarization(
    audio_path,
    prompt_name_mapping=False,
    language=None,
    asr_model=None,
    initial_prompt=None,
    pipeline=None,
    output_dir=None,
):
    ensure_nltk_tokenizers()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    lang = language or DEFAULT_LANGUAGE
    
    if pipeline:
        model = pipeline
    else:
        model_name = asr_model or ASR_MODEL
        model = whisperx.load_model(model_name, device, language=lang, compute_type=ASR_COMPUTE_TYPE)
        
    result = model.transcribe(audio_path, batch_size=16)
    
    # Alignment model is fast to load, but ideally should be cached too. For now, load per request.
    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], align_model, metadata, audio_path, device, return_char_alignments=False)

    wav, sr = librosa.load(audio_path, sr=16000)
    segments = []
    for seg in result["segments"]:
        s, e = int(seg["start"] * sr), int(seg["end"] * sr)
        if 0 <= s < e <= len(wav):
            segments.append(
                {
                    "wav": wav[s:e],
                    "text": seg.get("text", ""),
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "words": seg.get("words", []),
                }
            )

    clusters = []
    for i, seg in enumerate(segments):
        if len(seg["wav"]) < sr * 0.5:
            seg["speaker"] = "Unknown"
            continue
        try:
            proc = preprocess_wav(seg["wav"], source_sr=sr)
            emb = encoder.embed_utterance(proc)
            seg["embedding"] = emb
        except Exception:
            seg["speaker"] = "Unknown"
            continue

        assigned = False
        for cid, cl in enumerate(clusters):
            coef = np.dot(emb, cl["centroid"]) / (np.linalg.norm(emb) * np.linalg.norm(cl["centroid"]))
            if coef > 0.75:
                seg["speaker"] = f"Speaker_{cid}"
                cl["segments"].append(i)
                valid_embeds = [segments[j]["embedding"] for j in cl["segments"] if "embedding" in segments[j]]
                if valid_embeds:
                    cl["centroid"] = np.mean(valid_embeds, axis=0)
                assigned = True
                break

        if not assigned:
            seg["speaker"] = f"Speaker_{len(clusters)}"
            clusters.append({"centroid": emb, "segments": [i]})

    # IMPORTANT: Speaker "voiceprints" are used only in-memory for clustering within this
    # conversation. We do NOT persist speaker embeddings or profiles across sessions.
    name_map = {}

    base_name = os.path.splitext(os.path.basename(audio_path))[0] + "_diarized"
    out_dir = output_dir or TRANSCRIPT_FOLDER
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, base_name + ".txt")
    json_path = os.path.join(out_dir, base_name + ".json")

    # Write plain text transcript for compatibility.
    with open(out_path, 'w', encoding='utf-8') as f:
        for seg in segments:
            spk = seg.get("speaker", "Unknown")
            nm = name_map.get(spk, spk)
            txt = seg.get("text", "")
            f.write(f"[{nm}] {txt}\n")

    # Write structured transcript with timings and speaker mapping.
    structured = {
        "audio_path": audio_path,
        "language": result.get("language", lang),
        "segments": [],
        "speaker_map": name_map,
    }
    for seg in segments:
        spk = seg.get("speaker", "Unknown")
        structured["segments"].append(
            {
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "speaker": name_map.get(spk, spk),
                "text": seg.get("text", ""),
                "words": seg.get("words", []),
            }
        )
    try:
        with open(json_path, "w", encoding="utf-8") as jf:
            import json

            json.dump(structured, jf, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[warn] Failed to write structured transcript: {exc}")

    return out_path
