
import os
import datetime
import shutil
from pydub import AudioSegment
from diarizer import transcribe_with_diarization
from embedder import embed_text_file
from config import RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER, DB_PATH
import sqlite3

def import_external_recordings(import_folder="recordings/imported"):
    abs_path = os.path.abspath(import_folder)
    print(f"Checking import folder: {abs_path}")
    if not os.path.exists(import_folder):
        print(f"Import folder not found: {abs_path}")
        return
    print("Import folder found. Listing contents...")
    files = os.listdir(import_folder)
    if not files:
        print("Import folder is empty.")
        return
    print("Files:", files)

    if not os.path.exists(import_folder):
        print(f"No import folder found at {import_folder}")
        return

    print("Looking for files in:", import_folder)
    print("Files found:", os.listdir(import_folder))
    for file in files:
        if not file.lower().endswith(".mp3"):
            continue

        mp3_path = os.path.join(import_folder, file)
        base = os.path.splitext(file)[0]
        date_folder = datetime.datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        safe_base = base.replace(" ", "_").replace("/", "-")
        out_folder = os.path.join(RECORDINGS_FOLDER, date_folder)
        os.makedirs(out_folder, exist_ok=True)
        wav_name = f"{timestamp}_{safe_base}.wav"
        wav_path = os.path.join(out_folder, wav_name)

        print(f"Converting {file} to WAV...")
        audio = AudioSegment.from_mp3(mp3_path)
        audio.export(wav_path, format="wav")

        print(f"Transcribing with diarization: {wav_path}")
        transcript_path = transcribe_with_diarization(
            wav_path,
            prompt_name_mapping=False,
        )

        if transcript_path:
            # Move transcript to same subfolder
            transcript_target_folder = os.path.join(TRANSCRIPT_FOLDER, date_folder)
            os.makedirs(transcript_target_folder, exist_ok=True)
            transcript_target = os.path.join(transcript_target_folder, os.path.basename(transcript_path))
            shutil.move(transcript_path, transcript_target)
            structured_src = os.path.splitext(transcript_path)[0] + ".json"
            if os.path.exists(structured_src):
                structured_tgt = os.path.splitext(transcript_target)[0] + ".json"
                shutil.move(structured_src, structured_tgt)

            print(f"Embedding transcript: {transcript_target}")
            embedding_path = embed_text_file(transcript_target)

            # Move embedding to same subfolder
            embedding_target_folder = os.path.join(EMBEDDINGS_FOLDER, date_folder)
            os.makedirs(embedding_target_folder, exist_ok=True)
            if embedding_path and os.path.exists(embedding_path):
                embedding_target = os.path.join(embedding_target_folder, os.path.basename(embedding_path))
                shutil.move(embedding_path, embedding_target)
            else:
                embedding_target = None

            # Save session to database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO sessions (timestamp, title, tags, audio_path, transcript_path, embedding_path, diarized, embedded)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    datetime.datetime.now().isoformat(),
                    base,
                    "imported",
                    wav_path,
                    transcript_target,
                    embedding_target,
                    int(embedding_target is not None),
                ),
            )
            conn.commit()
            conn.close()

            print(f"Imported and processed: {file}")

        else:
            print(f"Transcription failed for {file}")

if __name__ == "__main__":
    import_external_recordings()
