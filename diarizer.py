import os
import numpy as np
import librosa
import torch
import whisperx
from resemblyzer import VoiceEncoder, preprocess_wav
from config import TRANSCRIPT_FOLDER
from voiceprints import load_voiceprints, save_voiceprints
from gui_helpers import prompt_speaker_name

encoder = VoiceEncoder()

def transcribe_with_diarization(audio_path, prompt_name_mapping=True):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = whisperx.load_model("medium", device, compute_type="float32")
    result = model.transcribe(audio_path, batch_size=16)
    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], align_model, metadata, audio_path, device, return_char_alignments=False)

    wav, sr = librosa.load(audio_path, sr=16000)
    segments = []
    for seg in result["segments"]:
        s, e = int(seg["start"] * sr), int(seg["end"] * sr)
        if 0 <= s < e <= len(wav):
            segments.append({"wav": wav[s:e], "text": seg["text"], "start": seg["start"], "end": seg["end"]})

    clusters = []
    for i, seg in enumerate(segments):
        if len(seg["wav"]) < sr * 0.5:
            seg["speaker"] = "Unknown"
            continue
        try:
            proc = preprocess_wav(seg["wav"], source_sr=sr)
            emb = encoder.embed_utterance(proc)
            seg["embedding"] = emb
        except:
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

    vps = load_voiceprints()
    name_map = {}

    if prompt_name_mapping:
        unique_speakers = {seg["speaker"] for seg in segments}
        for spk in unique_speakers:
            rep = next((s for s in segments if s.get("speaker") == spk and s.get("embedding") is not None), None)
            if rep:
                emb = rep["embedding"]
                match = next((info["name"] for info in vps.values()
                              if np.dot(emb, np.array(info["embedding"])) / (np.linalg.norm(emb) * np.linalg.norm(info["embedding"])) > 0.85), None)
                if match:
                    name_map[spk] = match
                else:
                    nm = prompt_speaker_name(spk, rep["text"], audio_path)
                    if nm:
                        name_map[spk] = nm
                        existing_match = None
                        for vid, v in vps.items():
                            if v["name"] == nm:
                                existing = np.array(v["embedding"])
                                sim = np.dot(emb, existing) / (np.linalg.norm(emb) * np.linalg.norm(existing))
                                if sim > 0.85:
                                    existing_match = vid
                                    break
                        if existing_match:
                            print(f"[Info] Merging with existing voiceprint for {nm} (ID: {existing_match})")
                            updated = np.mean([emb, np.array(vps[existing_match]["embedding"])], axis=0)
                            vps[existing_match]["embedding"] = updated.tolist()
                        else:
                            vps[f"voice_{len(vps)}"] = {"name": nm, "embedding": emb.tolist()}
                    else:
                        name_map[spk] = spk

    save_voiceprints(vps)

    from gui_debug import show_debug_overlay
    show_debug_overlay(segments)

    out_path = os.path.join(TRANSCRIPT_FOLDER, os.path.splitext(os.path.basename(audio_path))[0] + "_diarized.txt")
    with open(out_path, 'w', encoding='utf-8') as f:
        for seg in segments:
            spk = seg.get("speaker", "Unknown")
            nm = name_map.get(spk, spk)
            txt = seg.get("text", "")
            f.write(f"[{nm}] {txt}\n")

    return out_path
