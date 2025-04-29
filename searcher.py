
import os
import json
import numpy as np
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox, Listbox, Button, Label, Scrollbar, Toplevel
import requests
import shutil
from config import OLLAMA_URL, OLLAMA_EMBED_MODEL, EMBEDDINGS_FOLDER, TRANSCRIPT_FOLDER

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def embed_query(prompt):
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": prompt}
        )
        response.raise_for_status()
        return response.json().get("embedding")
    except Exception as e:
        messagebox.showerror("Embedding Error", str(e))
        return None

def search_and_export_transcripts():
    root = Toplevel()
    root.title("Semantic Search")

    Label(root, text="Enter your search prompt:").pack(pady=5)
    prompt_entry = tk.Text(root, height=5, width=60)
    prompt_entry.pack(padx=10)

    Label(root, text="Similarity threshold (0.0 - 1.0):").pack()
    threshold_entry = tk.Entry(root)
    threshold_entry.insert(0, "0.85")
    threshold_entry.pack(pady=5)

    results_box = Listbox(root, selectmode=tk.MULTIPLE, width=80, height=15)
    scrollbar = Scrollbar(root, command=results_box.yview)
    results_box.config(yscrollcommand=scrollbar.set)
    results_box.pack(padx=10, pady=5)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    matching_files = []

    def run_search():
        nonlocal matching_files
        results_box.delete(0, tk.END)
        prompt = prompt_entry.get("1.0", tk.END).strip()
        try:
            threshold = float(threshold_entry.get())
        except:
            messagebox.showerror("Invalid Threshold", "Enter a number between 0.0 and 1.0")
            return
        if not prompt:
            return

        query_embedding = embed_query(prompt)
        if query_embedding is None:
            return

        matches = []
        for root_dir, _, files in os.walk(EMBEDDINGS_FOLDER):
            for f in files:
                if not f.endswith(".json"):
                    continue
                emb_path = os.path.join(root_dir, f)
                try:
                    with open(emb_path, "r") as ef:
                        emb_data = json.load(ef)
                    similarity = cosine_similarity(query_embedding, emb_data["embedding"])
                    if similarity >= threshold:
                        matches.append((similarity, emb_path))
                except Exception as e:
                    print(f"Error reading {emb_path}: {e}")

        matches.sort(reverse=True)
        matching_files = matches
        for sim, path in matches:
            rel = os.path.relpath(path, EMBEDDINGS_FOLDER)
            results_box.insert(tk.END, f"{rel} (sim={sim:.3f})")

    def export_selected():
        indices = results_box.curselection()
        if not indices:
            return
        target = filedialog.askdirectory(title="Select export folder")
        if not target:
            return
        copied = 0
        for i in indices:
            rel_emb_path = matching_files[i][1]
            base = os.path.splitext(os.path.basename(rel_emb_path))[0]
            transcript_name = base + ".txt"
            found = False
            for root_dir, _, files in os.walk(TRANSCRIPT_FOLDER):
                for f in files:
                    if f.endswith(transcript_name):
                        src_path = os.path.join(root_dir, f)
                        dst_path = os.path.join(target, f)
                        shutil.copy(src_path, dst_path)
                        copied += 1
                        found = True
                        break
                if found:
                    break
        messagebox.showinfo("Export Complete", f"Exported {copied} transcript(s).")

    Button(root, text="Search", command=run_search).pack(pady=5)
    Button(root, text="Export Selected Transcripts", command=export_selected).pack(pady=5)

    root.grab_set()
    root.wait_window()
