import tkinter as tk
from tkinter import Toplevel, Label, Button, Entry, Listbox, Scrollbar, StringVar
from tkinter import ttk
import soundfile as sf
import sounddevice as sd
from voiceprints import load_voiceprints, save_voiceprints

def play_audio_snippet(wav_path, start_sec=0, duration_sec=3):
    try:
        start, stop = int(start_sec * 44100), int((start_sec + duration_sec) * 44100)
        data, fs = sf.read(wav_path, start=start, stop=stop)
        sd.play(data, samplerate=fs)
        sd.wait()
    except Exception as e:
        print(f"Audio playback error: {e}")

def prompt_speaker_name(speaker, sample_text, audio_path):
    result = {"name": None}

    dialog = Toplevel()
    dialog.title("Identify Speaker")

    Label(dialog, text=f"Sample from {speaker}:").pack(pady=5)
    Label(dialog, text=f"\"{sample_text}\"").pack(pady=5)
    Button(dialog, text="▶ Play Sample", command=lambda: play_audio_snippet(audio_path)).pack(pady=5)

    vp_data = load_voiceprints()
    existing_names = sorted({v["name"] for v in vp_data.values()})
    selected_name = StringVar()
    dropdown = ttk.Combobox(dialog, values=existing_names, textvariable=selected_name)
    dropdown.pack(pady=5)

    entry = Entry(dialog)
    entry.pack(pady=5)

    def on_select(event):
        entry.delete(0, 'end')
        entry.insert(0, dropdown.get())

    dropdown.bind("<<ComboboxSelected>>", on_select)

    def on_submit():
        result["name"] = entry.get().strip()
        dialog.destroy()

    def on_skip():
        result["name"] = None
        dialog.destroy()

    Button(dialog, text="Confirm", command=on_submit).pack(side='left', padx=10, pady=10)
    Button(dialog, text="Skip", command=on_skip).pack(side='right', padx=10, pady=10)

    dialog.grab_set()
    dialog.wait_window()

    return result["name"]

def manage_voiceprints_ui():
    voiceprints = load_voiceprints()
    dialog = Toplevel()
    dialog.title("Manage Speaker Names")

    Label(dialog, text="Stored Speaker Names").pack()
    listbox = Listbox(dialog, width=40)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll = Scrollbar(dialog, command=listbox.yview)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.config(yscrollcommand=scroll.set)

    for k, v in voiceprints.items():
        listbox.insert(tk.END, f"{v['name']} (ID: {k})")

    def delete_selected():
        selection = listbox.curselection()
        if selection:
            text = listbox.get(selection[0])
            speaker_id = text.split("ID: ")[-1].strip(")")
            del voiceprints[speaker_id]
            listbox.delete(selection[0])
            save_voiceprints(voiceprints)

    Button(dialog, text="Delete Selected", command=delete_selected).pack(pady=5)
    dialog.grab_set()
    dialog.wait_window()

    dlg.title("File Management")

    Label(dlg, text="Recordings").grid(row=0, column=0, padx=5, pady=5)
    Label(dlg, text="Transcripts").grid(row=0, column=1, padx=5, pady=5)
    Label(dlg, text="Embeddings").grid(row=0, column=2, padx=5, pady=5)

    recs = Listbox(dlg, height=15, width=30)
    recs.grid(row=1, column=0, padx=5)
    for item in list_recordings():
        recs.insert(tk.END, item)

    trans = Listbox(dlg, height=15, width=30)
    trans.grid(row=1, column=1, padx=5)
    for item in list_transcripts():
        trans.insert(tk.END, item)

    embs = Listbox(dlg, height=15, width=30)
    embs.grid(row=1, column=2, padx=5)
    for item in list_embeddings():
        embs.insert(tk.END, item)

    def refresh():
        recs.delete(0, tk.END)
        trans.delete(0, tk.END)
        embs.delete(0, tk.END)
        for item in list_recordings():
            recs.insert(tk.END, item)
        for item in list_transcripts():
            trans.insert(tk.END, item)
        for item in list_embeddings():
            embs.insert(tk.END, item)

    Button(dlg, text="Refresh", command=refresh).grid(row=2, column=1, pady=10)
    dlg.grab_set()
    dlg.wait_window()


from config import RECORDINGS_FOLDER
import datetime
import os

def prompt_for_filename():
    from config import RECORDINGS_FOLDER
    from tkinter import Toplevel, Label, Entry, Button
    result = {"filename": None, "folder": None, "tags": "", "title": ""}

    dialog = Toplevel()
    dialog.title("Recording Description")

    Label(dialog, text="Enter meeting title or description:").pack(padx=10, pady=5)
    entry_title = Entry(dialog, width=50)
    entry_title.pack(padx=10, pady=5)

    Label(dialog, text="Enter tags (comma separated):").pack(padx=10, pady=5)
    entry_tags = Entry(dialog, width=50)
    entry_tags.pack(padx=10, pady=5)

    def confirm():
        title_val = entry_title.get().strip()
        tags_val = entry_tags.get().strip()
        if title_val:
            date_folder = datetime.datetime.now().strftime("%Y-%m-%d")
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            safe_name = title_val.replace(" ", "_").replace("/", "-")
            folder_path = os.path.join(RECORDINGS_FOLDER, date_folder)
            os.makedirs(folder_path, exist_ok=True)
            result["filename"] = f"{timestamp}_{safe_name}.wav"
            result["folder"] = folder_path
            result["tags"] = tags_val
            result["title"] = title_val
            dialog.destroy()

    Button(dialog, text="Confirm", command=confirm).pack(pady=10)
    dialog.grab_set()
    dialog.wait_window()
    return result

    import sqlite3
    from config import DB_PATH, RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER

    dlg = Toplevel()
    dlg.title("File Management")

    Label(dlg, text="Recordings").grid(row=0, column=0, padx=5, pady=5)
    Label(dlg, text="Transcripts").grid(row=0, column=1, padx=5, pady=5)
    Label(dlg, text="Embeddings").grid(row=0, column=2, padx=5, pady=5)

    recs = Listbox(dlg, height=15, width=30)
    recs.grid(row=1, column=0, padx=5)
    trans = Listbox(dlg, height=15, width=30)
    trans.grid(row=1, column=1, padx=5)
    embs = Listbox(dlg, height=15, width=30)
    embs.grid(row=1, column=2, padx=5)

    def refresh():
        recs.delete(0, tk.END)
        trans.delete(0, tk.END)
        embs.delete(0, tk.END)
        for item in list_recordings():
            recs.insert(tk.END, item)
        for item in list_transcripts():
            trans.insert(tk.END, item)
        for item in list_embeddings():
            embs.insert(tk.END, item)

    def on_rec_select(event):
        selection = recs.curselection()
        if not selection:
            return
        rec_file = recs.get(selection[0])
        base = os.path.splitext(os.path.basename(rec_file))[0]
        # Try to select matching transcript and embedding
        for i in range(trans.size()):
            if os.path.basename(trans.get(i)).startswith(base):
                trans.selection_clear(0, tk.END)
                trans.selection_set(i)
                break
        for i in range(embs.size()):
            if os.path.basename(embs.get(i)).startswith(base):
                embs.selection_clear(0, tk.END)
                embs.selection_set(i)
                break

    def delete_selected_session():
        sel = recs.curselection()
        if not sel:
            return
        audio = recs.get(sel[0])
        base = os.path.splitext(os.path.basename(audio))[0]

        audio_path = os.path.join(RECORDINGS_FOLDER, audio)
        transcript_path = os.path.join(TRANSCRIPT_FOLDER, base + "_diarized.txt")
        embedding_path = os.path.join(EMBEDDINGS_FOLDER, base + ".json")

        # Remove files if they exist
        for path in [audio_path, transcript_path, embedding_path]:
            if os.path.exists(path):
                os.remove(path)
                print(f"Deleted {path}")

        # Remove from database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE audio_path = ?", (os.path.join(RECORDINGS_FOLDER, audio),))
        conn.commit()
        conn.close()

        refresh()

    recs.bind("<<ListboxSelect>>", on_rec_select)

    Button(dlg, text="Delete Selected Session", command=delete_selected_session).grid(row=2, column=0, pady=10)
    Button(dlg, text="Refresh", command=refresh).grid(row=2, column=1, pady=10)

    refresh()
    dlg.grab_set()
    dlg.wait_window()

    import sqlite3
    from config import DB_PATH, RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER

    dlg = Toplevel()
    dlg.title("File Management")

    Label(dlg, text="Recordings").grid(row=0, column=0, padx=5, pady=5)
    Label(dlg, text="Transcripts").grid(row=0, column=1, padx=5, pady=5)
    Label(dlg, text="Embeddings").grid(row=0, column=2, padx=5, pady=5)

    recs = Listbox(dlg, height=15, width=30)
    recs.grid(row=1, column=0, padx=5)
    trans = Listbox(dlg, height=15, width=30)
    trans.grid(row=1, column=1, padx=5)
    embs = Listbox(dlg, height=15, width=30)
    embs.grid(row=1, column=2, padx=5)

    def refresh():
        recs.delete(0, tk.END)
        trans.delete(0, tk.END)
        embs.delete(0, tk.END)
        for item in list_recordings():
            recs.insert(tk.END, item)
        for item in list_transcripts():
            trans.insert(tk.END, item)
        for item in list_embeddings():
            embs.insert(tk.END, item)

    def on_rec_select(event):
        selection = recs.curselection()
        if not selection:
            return
        rec_file = recs.get(selection[0])
        base = os.path.splitext(os.path.basename(rec_file))[0]
        # Try to select matching transcript and embedding
        for i in range(trans.size()):
            if os.path.basename(trans.get(i)).startswith(base):
                trans.selection_clear(0, tk.END)
                trans.selection_set(i)
                break
        for i in range(embs.size()):
            if os.path.basename(embs.get(i)).startswith(base):
                embs.selection_clear(0, tk.END)
                embs.selection_set(i)
                break

    def find_file_by_basename(folder, basename):
        for root, _, files in os.walk(folder):
            for f in files:
                if f.startswith(basename):
                    return os.path.join(root, f)
        return None

    def delete_selected_session():
        sel = recs.curselection()
        if not sel:
            return
        audio = recs.get(sel[0])
        base = os.path.splitext(os.path.basename(audio))[0]

        audio_path = os.path.join(RECORDINGS_FOLDER, audio)
        transcript_path = find_file_by_basename(TRANSCRIPT_FOLDER, base + "_diarized.txt")
        embedding_path = find_file_by_basename(EMBEDDINGS_FOLDER, base + ".json")

        for path in [audio_path, transcript_path, embedding_path]:
            if path and os.path.exists(path):
                os.remove(path)
                print(f"Deleted {path}")
                folder = os.path.dirname(path)
                if not os.listdir(folder):
                    os.rmdir(folder)
                    print(f"Removed empty folder: {folder}")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE audio_path = ?", (os.path.join(RECORDINGS_FOLDER, audio),))
        conn.commit()
        conn.close()

        refresh()

    recs.bind("<<ListboxSelect>>", on_rec_select)

    Button(dlg, text="Delete Selected Session", command=delete_selected_session).grid(row=2, column=0, pady=10)
    Button(dlg, text="Refresh", command=refresh).grid(row=2, column=1, pady=10)

    refresh()
    dlg.grab_set()
    dlg.wait_window()

    import sqlite3
    from config import DB_PATH, RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER

    dlg = Toplevel()
    dlg.title("File Management")

    Label(dlg, text="Recordings").grid(row=0, column=0, padx=5, pady=5)
    Label(dlg, text="Transcripts").grid(row=0, column=1, padx=5, pady=5)
    Label(dlg, text="Embeddings").grid(row=0, column=2, padx=5, pady=5)

    recs = Listbox(dlg, height=15, width=30)
    recs.grid(row=1, column=0, padx=5)
    trans = Listbox(dlg, height=15, width=30)
    trans.grid(row=1, column=1, padx=5)
    embs = Listbox(dlg, height=15, width=30)
    embs.grid(row=1, column=2, padx=5)

    def refresh():
        recs.delete(0, tk.END)
        trans.delete(0, tk.END)
        embs.delete(0, tk.END)
        for item in list_recordings():
            recs.insert(tk.END, item)
        for item in list_transcripts():
            trans.insert(tk.END, item)
        for item in list_embeddings():
            embs.insert(tk.END, item)

    def on_rec_select(event):
        selection = recs.curselection()
        if not selection:
            return
        rec_file = recs.get(selection[0])
        base = os.path.splitext(rec_file)[0]  # Includes subfolder
        # Try to select matching transcript and embedding
        for i in range(trans.size()):
            if os.path.splitext(trans.get(i))[0] == base + "_diarized":
                trans.selection_clear(0, tk.END)
                trans.selection_set(i)
                break
        for i in range(embs.size()):
            if os.path.splitext(embs.get(i))[0] == base + "_diarized":
                embs.selection_clear(0, tk.END)
                embs.selection_set(i)
                break

    def find_file_by_relpath(folder, rel_path):
        for root, _, files in os.walk(folder):
            for f in files:
                if os.path.join(os.path.relpath(root, folder), f) == rel_path:
                    return os.path.join(root, f)
        return None

    def delete_selected_session():
        sel = recs.curselection()
        if not sel:
            return
        audio_rel = recs.get(sel[0])
        base_rel = os.path.splitext(audio_rel)[0]
        audio_path = os.path.join(RECORDINGS_FOLDER, audio_rel)
        transcript_rel = base_rel + "_diarized.txt"
        embedding_rel = base_rel + "_diarized.json"

        transcript_path = find_file_by_relpath(TRANSCRIPT_FOLDER, transcript_rel)
        embedding_path = find_file_by_relpath(EMBEDDINGS_FOLDER, embedding_rel)

        for path in [audio_path, transcript_path, embedding_path]:
            if path and os.path.exists(path):
                os.remove(path)
                print(f"Deleted {path}")
                folder = os.path.dirname(path)
                if not os.listdir(folder):
                    os.rmdir(folder)
                    print(f"Removed empty folder: {folder}")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE audio_path = ?", (audio_path,))
        conn.commit()
        conn.close()

        refresh()

    recs.bind("<<ListboxSelect>>", on_rec_select)

    Button(dlg, text="Delete Selected Session", command=delete_selected_session).grid(row=2, column=0, pady=10)
    Button(dlg, text="Refresh", command=refresh).grid(row=2, column=1, pady=10)

    refresh()
    dlg.grab_set()
    dlg.wait_window()

    import sqlite3
    from config import DB_PATH, RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER

    dlg = Toplevel()
    dlg.title("File Management")

    Label(dlg, text="Recordings").grid(row=0, column=0, padx=5, pady=5)
    Label(dlg, text="Transcripts").grid(row=0, column=1, padx=5, pady=5)
    Label(dlg, text="Embeddings").grid(row=0, column=2, padx=5, pady=5)

    recs = Listbox(dlg, height=15, width=30)
    recs.grid(row=1, column=0, padx=5)
    trans = Listbox(dlg, height=15, width=30)
    trans.grid(row=1, column=1, padx=5)
    embs = Listbox(dlg, height=15, width=30)
    embs.grid(row=1, column=2, padx=5)

    def refresh():
        recs.delete(0, tk.END)
        trans.delete(0, tk.END)
        embs.delete(0, tk.END)
        for item in list_recordings():
            recs.insert(tk.END, item)
        for item in list_transcripts():
            trans.insert(tk.END, item)
        for item in list_embeddings():
            embs.insert(tk.END, item)

    def on_rec_select(event):
        selection = recs.curselection()
        if not selection:
            return
        rec_file = recs.get(selection[0])
        base = os.path.splitext(rec_file)[0]
        for i in range(trans.size()):
            if os.path.splitext(trans.get(i))[0] == base + "_diarized":
                trans.selection_clear(0, tk.END)
                trans.selection_set(i)
                break
        for i in range(embs.size()):
            if os.path.splitext(embs.get(i))[0] == base + "_diarized":
                embs.selection_clear(0, tk.END)
                embs.selection_set(i)
                break

    def find_file_by_relpath(folder, rel_path):
        for root, _, files in os.walk(folder):
            for f in files:
                full_rel = os.path.join(os.path.relpath(root, folder), f)
                if full_rel == rel_path:
                    return os.path.join(root, f)
        return None

    def delete_selected_session():
        sel = recs.curselection()
        if not sel:
            print("No recording selected.")
            return
        audio_rel = recs.get(sel[0])
        base_rel = os.path.splitext(audio_rel)[0]
        print(f"Selected base: {base_rel}")
        audio_path = os.path.join(RECORDINGS_FOLDER, audio_rel)
        transcript_rel = base_rel + "_diarized.txt"
        embedding_rel = base_rel + "_diarized.json"

        print(f"Audio path: {audio_path}")
        transcript_path = find_file_by_relpath(TRANSCRIPT_FOLDER, transcript_rel)
        embedding_path = find_file_by_relpath(EMBEDDINGS_FOLDER, embedding_rel)
        print(f"Transcript path: {transcript_path}")
        print(f"Embedding path: {embedding_path}")

        for path in [audio_path, transcript_path, embedding_path]:
            if path and os.path.exists(path):
                os.remove(path)
                print(f"Deleted {path}")
                folder = os.path.dirname(path)
                if not os.listdir(folder):
                    os.rmdir(folder)
                    print(f"Removed empty folder: {folder}")
            else:
                print(f"File not found or already deleted: {path}")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE audio_path = ?", (audio_path,))
        conn.commit()
        conn.close()
        print(f"Deleted from database: {audio_path}")

        refresh()

    recs.bind("<<ListboxSelect>>", on_rec_select)

    Button(dlg, text="Delete Selected Session", command=delete_selected_session).grid(row=2, column=0, pady=10)
    Button(dlg, text="Refresh", command=refresh).grid(row=2, column=1, pady=10)

    refresh()
    dlg.grab_set()
    dlg.wait_window()

def file_management_ui(list_recordings, list_transcripts, list_embeddings):
    import os
    import sqlite3
    from config import DB_PATH, RECORDINGS_FOLDER, TRANSCRIPT_FOLDER, EMBEDDINGS_FOLDER

    dlg = Toplevel()
    dlg.title("File Management")

    Label(dlg, text="Recordings").grid(row=0, column=0, padx=5, pady=5)
    Label(dlg, text="Transcripts").grid(row=0, column=1, padx=5, pady=5)
    Label(dlg, text="Embeddings").grid(row=0, column=2, padx=5, pady=5)

    recs = Listbox(dlg, height=15, width=30)
    recs.grid(row=1, column=0, padx=5)
    trans = Listbox(dlg, height=15, width=30)
    trans.grid(row=1, column=1, padx=5)
    embs = Listbox(dlg, height=15, width=30)
    embs.grid(row=1, column=2, padx=5)

    def refresh():
        recs.delete(0, tk.END)
        trans.delete(0, tk.END)
        embs.delete(0, tk.END)
        for item in list_recordings():
            recs.insert(tk.END, item)
        for item in list_transcripts():
            trans.insert(tk.END, item)
        for item in list_embeddings():
            embs.insert(tk.END, item)

    def on_rec_select(event):
        selection = recs.curselection()
        if not selection:
            return
        rec_file = recs.get(selection[0])
        base = os.path.splitext(rec_file)[0]
        for i in range(trans.size()):
            if os.path.splitext(trans.get(i))[0] == base + "_diarized":
                trans.selection_clear(0, tk.END)
                trans.selection_set(i)
                break
        for i in range(embs.size()):
            if os.path.splitext(embs.get(i))[0] == base + "_diarized":
                embs.selection_clear(0, tk.END)
                embs.selection_set(i)
                break

    def find_file_by_relpath(folder, rel_path):
        for root, _, files in os.walk(folder):
            for f in files:
                full_rel = os.path.join(os.path.relpath(root, folder), f)
                if full_rel == rel_path:
                    return os.path.join(root, f)
        return None

    def delete_selected_session():
        if recs.curselection():
            audio_rel = recs.get(recs.curselection()[0])
        else:
            audio_rel = recs.get(tk.ACTIVE)
        if not audio_rel:
            print("No recording selected.")
            return

        base_rel = os.path.splitext(audio_rel)[0]
        print(f"Selected base: {base_rel}")
        audio_path = os.path.join(RECORDINGS_FOLDER, audio_rel)
        transcript_rel = base_rel + "_diarized.txt"
        embedding_rel = base_rel + "_diarized.json"

        print(f"Audio path: {audio_path}")
        transcript_path = find_file_by_relpath(TRANSCRIPT_FOLDER, transcript_rel)
        embedding_path = find_file_by_relpath(EMBEDDINGS_FOLDER, embedding_rel)
        print(f"Transcript path: {transcript_path}")
        print(f"Embedding path: {embedding_path}")

        for path in [audio_path, transcript_path, embedding_path]:
            if path and os.path.exists(path):
                os.remove(path)
                print(f"Deleted {path}")
                folder = os.path.dirname(path)
                if not os.listdir(folder):
                    os.rmdir(folder)
                    print(f"Removed empty folder: {folder}")
            else:
                print(f"File not found or already deleted: {path}")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE audio_path = ?", (audio_path,))
        conn.commit()
        conn.close()
        print(f"Deleted from database: {audio_path}")

        refresh()

    recs.bind("<<ListboxSelect>>", on_rec_select)

    Button(dlg, text="Delete Selected Session", command=delete_selected_session).grid(row=2, column=0, pady=10)
    Button(dlg, text="Refresh", command=refresh).grid(row=2, column=1, pady=10)

    refresh()
    dlg.grab_set()
    dlg.wait_window()