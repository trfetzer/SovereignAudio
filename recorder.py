import os
from gui_helpers import prompt_for_filename
import datetime
import sounddevice as sd
import soundfile as sf
from database import insert_session
from config import RECORDINGS_FOLDER

class Recorder:
    def __init__(self):
        self.stream = None
        self.file = None
        self.paused = False
        self.record_info = None
        self.last_audio = None


    def prompt_for_filename(self):
        return prompt_for_filename()

    def audio_callback(self, indata, frames, time_info, status):
        if not self.paused and self.file:
            self.file.write(indata.copy())

    def start_recording(self, info):
        path = os.path.join(info["folder"], info["filename"])
        self.record_info = info
        self.file = sf.SoundFile(path, mode='w', samplerate=44100, channels=1)
        self.stream = sd.InputStream(samplerate=44100, channels=1, callback=self.audio_callback)
        self.stream.start()
        self.paused = False

    def pause_recording(self):
        if self.stream:
            self.paused = not self.paused

    def stop_recording(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.file:
            self.file.close()
            saved = os.path.join(self.record_info["folder"], self.record_info["filename"])
            self.last_audio = saved
            insert_session(
                timestamp=datetime.datetime.now().isoformat(),
                title=self.record_info["title"],
                tags=self.record_info["tags"],
                audio_path=saved
            )
            return saved
        return None
