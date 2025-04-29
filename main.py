import datetime
import os
import threading
import tkinter as tk
from tkinter import messagebox

from config import *
from database import init_db, update_transcript, update_embedding
from recorder import Recorder
from diarizer import transcribe_with_diarization
from embedder import embed_text_file
from voiceprints import load_voiceprints, save_voiceprints
from file_manager import list_recordings, list_transcripts, list_embeddings
from gui_helpers import prompt_speaker_name, play_audio_snippet, manage_voiceprints_ui, file_management_ui
from searcher import search_and_export_transcripts

# Initialize database and folders
init_db()
os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)
os.makedirs(RECORDINGS_FOLDER, exist_ok=True)
os.makedirs(EMBEDDINGS_FOLDER, exist_ok=True)

class MomoApp:
    def __init__(self, master):
        self.master = master
        master.title("Local Voice Memo and Transcription Tool")

        tk.Label(master, text="Click to manage recording").pack(pady=10)
        self.recorder = Recorder()
        self.start_btn = tk.Button(master, text="Start Recording", command=self.start_recording)
        self.start_btn.pack(pady=5)
        self.pause_btn = tk.Button(master, text="Pause Recording", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(pady=5)
        self.stop_btn = tk.Button(master, text="Stop Recording", command=self.stop_recording, state=tk.DISABLED)
        self.stop_btn.pack(pady=5)
        self.search_button = tk.Button(master, text="🔍 Semantic Search", command=search_and_export_transcripts)
        self.search_button.pack(pady=5)
        tk.Button(master, text="Transcribe with Diarization", command=self.transcribe_last).pack(pady=5)
        tk.Button(master, text="Embed Last Transcript", command=self.embed_last).pack(pady=5)
        tk.Button(master, text="Manage Speaker Names", command=manage_voiceprints_ui).pack(pady=5)
        tk.Button(master, text="Manage Files", command=lambda: file_management_ui(list_recordings, list_transcripts, list_embeddings)).pack(pady=5)

        self.status = tk.Label(master, text="Status: Ready")
        self.status.pack(pady=10)

        self.last_audio = None
        self.last_transcript = None

    def start_recording(self):
        info = self.recorder.prompt_for_filename()
        if not info.get("filename"):
            self.status.config(text="Recording cancelled.")
            return
        # ensure folder exists
        os.makedirs(info["folder"], exist_ok=True)

        self.recorder.start_recording(info)
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.status.config(text="Recording...")

    def toggle_pause(self):
        self.recorder.pause_recording()
        paused = self.recorder.paused
        self.pause_btn.config(text="Resume Recording" if paused else "Pause Recording")
        self.status.config(text="Recording Paused" if paused else "Recording...")

    def stop_recording(self):
        saved = self.recorder.stop_recording()
        if saved:
            self.last_audio = saved
            self.status.config(text=f"Recorded: {saved}")
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)

    def transcribe_last(self):
        if not self.last_audio:
            messagebox.showerror("No Audio","Record audio first!")
            return
        self.status.config(text="Transcribing...")
        def task():
            transcript = transcribe_with_diarization(self.last_audio)
            df = os.path.basename(os.path.dirname(self.last_audio))
            outd = os.path.join(TRANSCRIPT_FOLDER, df)
            os.makedirs(outd, exist_ok=True)
            tgt = os.path.join(outd, os.path.basename(transcript))
            os.replace(transcript, tgt)
            update_transcript(self.last_audio, tgt)
            self.last_transcript = tgt
            self.status.config(text=f"Transcript saved: {tgt}")
        threading.Thread(target=task).start()

    def embed_last(self):
        if not self.last_transcript:
            messagebox.showerror("No Transcript","Transcribe audio first!")
            return
        self.status.config(text="Embedding...")
        def task():
            emb = embed_text_file(self.last_transcript)
            if emb:
                df = os.path.basename(os.path.dirname(self.last_transcript))
                outd = os.path.join(EMBEDDINGS_FOLDER, df)
                os.makedirs(outd, exist_ok=True)
                tgt = os.path.join(outd, os.path.basename(emb))
                os.replace(emb, tgt)
                update_embedding(self.last_transcript, tgt)
                self.status.config(text=f"Embedded: {tgt}")
            else:
                self.status.config(text="Embedding failed.")
        threading.Thread(target=task).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = MomoApp(root)
    root.mainloop()
