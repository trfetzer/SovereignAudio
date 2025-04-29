
import tkinter as tk
from tkinter import Toplevel, Label, Entry, Button, Scrollbar, Listbox, Scale, HORIZONTAL, messagebox
import json
import os
from voiceprints import load_voiceprints, save_voiceprints

def show_debug_overlay(segments):
    win = Toplevel()
    win.title("Speaker Assignment Debug Overlay")

    listbox = Listbox(win, width=100, height=25)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = Scrollbar(win, command=listbox.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.config(yscrollcommand=scrollbar.set)

    for seg in segments:
        speaker = seg.get("speaker", "Unknown")
        text = seg.get("text", "")
        line = f"[{speaker}] {text} ({seg.get('start'):.2f} - {seg.get('end'):.2f}s)"
        listbox.insert(tk.END, line)

    win.grab_set()
    win.wait_window()

def edit_speaker_names():
    voiceprints = load_voiceprints()
    if not voiceprints:
        messagebox.showinfo("Info", "No voiceprints found.")
        return

    win = Toplevel()
    win.title("Edit Speaker Names")

    Label(win, text="Stored Speaker Profiles").pack()
    listbox = Listbox(win, width=50)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll = Scrollbar(win, command=listbox.yview)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.config(yscrollcommand=scroll.set)

    for k, v in voiceprints.items():
        listbox.insert(tk.END, f"{v['name']} (ID: {k})")

    name_entry = Entry(win, width=30)
    name_entry.pack(pady=5)

    def update_name():
        sel = listbox.curselection()
        if not sel:
            return
        new_name = name_entry.get().strip()
        if new_name:
            idx = sel[0]
            item_text = listbox.get(idx)
            voice_id = item_text.split("ID: ")[-1].strip(")")
            voiceprints[voice_id]["name"] = new_name
            listbox.delete(idx)
            listbox.insert(idx, f"{new_name} (ID: {voice_id})")
            save_voiceprints(voiceprints)

    Button(win, text="Update Name", command=update_name).pack(pady=5)
    win.grab_set()
    win.wait_window()
