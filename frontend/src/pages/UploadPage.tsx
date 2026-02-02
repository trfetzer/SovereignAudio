import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { embedSession, getSettings, transcribeSession, uploadFile } from "../api";

type StepState = "idle" | "working" | "done" | "error";

export default function UploadPage() {
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const location = useLocation();

  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("en");
  const [log, setLog] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);
  const [showRecorder, setShowRecorder] = useState(false);
  const [steps, setSteps] = useState<{ upload: StepState; transcribe: StepState; embed: StepState }>({
    upload: "idle",
    transcribe: "idle",
    embed: "idle",
  });
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [transcriptPath, setTranscriptPath] = useState<string | null>(null);
  const [embeddingPath, setEmbeddingPath] = useState<string | null>(null);

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("record") === "1") {
      setShowRecorder(true);
    }
  }, [location.search]);

  const pushLog = (msg: string) => setLog((prev) => [...prev, msg]);

  const reset = () => {
    setSteps({ upload: "idle", transcribe: "idle", embed: "idle" });
    setSessionId(null);
    setTranscriptPath(null);
    setEmbeddingPath(null);
    setLog([]);
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
        const ext = mimeType.split("/")[1];
        const blob = new Blob(chunksRef.current, { type: mimeType });
        const filename = `recording_${new Date().toISOString().replace(/[:.]/g, "-")}.${ext}`;
        const recordedFile = new File([blob], filename, { type: mimeType });
        setFile(recordedFile);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      timerRef.current = window.setInterval(() => {
        setRecordingTime((t) => t + 1);
      }, 1000);
    } catch (err: any) {
      alert("Could not start recording: " + err.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const ensureEmbed = async (sid: string, maybeExisting?: string | null) => {
    if (maybeExisting) return maybeExisting;
    const res = await embedSession(sid);
    return res.embedding_path;
  };

  const start = async () => {
    if (!file) return;
    reset();
    try {
      setSteps((s) => ({ ...s, upload: "working" }));
      pushLog("Uploading file…");
      const up = await uploadFile(file);
      setSessionId(up.session_id);
      setSteps((s) => ({ ...s, upload: "done" }));
      pushLog(`Uploaded session: ${up.session_id}`);

      setSteps((s) => ({ ...s, transcribe: "working" }));
      pushLog("Transcribing with diarization…");
      const t = await transcribeSession(up.session_id, language);
      setTranscriptPath(t.transcript_path);
      setSteps((s) => ({ ...s, transcribe: "done" }));
      pushLog(`Transcript: ${t.transcript_path}`);

      setSteps((s) => ({ ...s, embed: "working" }));
      const embPath = await ensureEmbed(up.session_id, t.embedding_path || null);
      setEmbeddingPath(embPath || null);
      setSteps((s) => ({ ...s, embed: "done" }));
      pushLog(embPath ? `Embedding complete: ${embPath}` : "Embedding skipped.");
    } catch (err: any) {
      console.error(err);
      pushLog("Error: " + (err.message || "Unknown error"));
      setSteps((s) => {
        const copy = { ...s };
        for (const k of Object.keys(copy)) {
          if (copy[k as keyof typeof copy] === "working") copy[k as keyof typeof copy] = "error";
        }
        return copy;
      });
    }
  };

  const indicator = (state: StepState) => {
    if (state === "working") return "⏳";
    if (state === "done") return "✅";
    if (state === "error") return "⚠️";
    return "•";
  };

  return (
    <div className="card">
      <h2>Upload & Process Audio</h2>
      <p style={{ color: "#9ca3af", marginTop: 0 }}>
        Drop a file or record in-browser, then we’ll diarize, transcribe, and embed it. {settings?.auto_embed ? "Auto-embed is enabled." : "Embedding will run after transcription."}
      </p>

      <div className="card" style={{ background: "#131822", borderColor: "#1f2a3a" }}>
        <h3>Step 1 — Add Audio</h3>
        <div className="row" style={{ gap: 10 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <button className="btn secondary" onClick={() => fileInputRef.current?.click()}>
            Choose audio file
          </button>
          <input className="input" style={{ width: 140 }} value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="lang" />
          <button className="btn" onClick={start} disabled={!file}>
            {file ? "Process" : "Select File"}
          </button>
        </div>
        {file && <div style={{ marginTop: 8, fontSize: 14, color: "#9ca3af" }}>Selected: {file.name}</div>}

        <button className="btn secondary" style={{ marginTop: 12 }} onClick={() => setShowRecorder((v) => !v)}>
          {showRecorder ? "Hide" : "Show"} browser recorder
        </button>
        {showRecorder && (
          <div className="card" style={{ marginTop: 12, background: "#0f131b", borderColor: "#1d2431" }}>
            <h4>Record in browser</h4>
            <div className="row">
              {!isRecording ? (
                <button className="btn" onClick={startRecording}>
                  Start Recording
                </button>
              ) : (
                <button className="btn danger" onClick={stopRecording}>
                  Stop Recording ({formatTime(recordingTime)})
                </button>
              )}
            </div>
            <p style={{ color: "#94a3b8" }}>Recording uses your browser mic. Stop to attach the captured file above.</p>
          </div>
        )}
      </div>

      <div className="card" style={{ background: "#11151c" }}>
        <h3>Step 2 — Processing</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 8 }}>
          <div className="progress-row">
            <span>Upload</span>
            <span>{indicator(steps.upload)}</span>
          </div>
          <div className="progress-row">
            <span>Transcribe</span>
            <span>{indicator(steps.transcribe)}</span>
          </div>
          <div className="progress-row">
            <span>Embed</span>
            <span>{indicator(steps.embed)}</span>
          </div>
        </div>

        <button className="btn secondary" style={{ marginTop: 12 }} onClick={() => setShowLog((v) => !v)}>
          {showLog ? "Hide details" : "Show details"}
        </button>
        {showLog && (
          <div className="log-box">
            <pre>{log.join("\n") || "No activity yet."}</pre>
          </div>
        )}

        {sessionId && (
          <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
            <a className="btn secondary" href={`/sessions/${encodeURIComponent(sessionId)}`}>
              Open Transcript
            </a>
            {embeddingPath && (
              <span className="badge" style={{ background: "#133352", color: "#9cc4ff" }}>
                Embedded
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
