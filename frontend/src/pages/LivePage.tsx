import { useState, useRef, useEffect } from "react";
import { API_BASE } from "../api";

export default function LivePage() {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [transcript, setTranscript] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = recorder;

      // Connect to WebSocket
      const wsUrl = API_BASE.replace("http", "ws") + "/ws/live";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("Recording...");
        setIsRecording(true);
        recorder.start(1000); // Send chunks every 1s
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "session" && msg.session_id) {
            setSessionId(msg.session_id);
            return;
          }
          if (msg.type === "partial") {
            setTranscript([msg.text || ""]);
            return;
          }
        } catch {
          // fallback: treat as plain text
          setTranscript([String(event.data || "")]);
        }
      };

      ws.onclose = () => {
        setStatus("Disconnected");
        setIsRecording(false);
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        setStatus("Error");
      };

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };

    } catch (err: any) {
      alert("Could not start recording: " + err.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setStatus("Stopped");
    }
  };

  return (
    <div className="card">
      <h2>Live Transcription</h2>
      <div className="row" style={{ marginBottom: 16 }}>
        {!isRecording ? (
          <button className="btn" onClick={startRecording}>
            Start Live Session
          </button>
        ) : (
          <button className="btn" style={{ background: "#ef4444" }} onClick={stopRecording}>
            Stop Session
          </button>
        )}
        <div>Status: {status}</div>
      </div>

      {sessionId && (
        <div style={{ marginBottom: 12 }}>
          <a className="btn secondary" href={`/sessions/${encodeURIComponent(sessionId)}`}>
            Open session
          </a>
        </div>
      )}

      <div className="card" style={{ background: "#171c24", minHeight: 300, maxHeight: "60vh", overflow: "auto" }}>
        {transcript.length === 0 ? (
          <p style={{ color: "#6b7280" }}>Transcript will appear here...</p>
        ) : (
          transcript.map((line, i) => <div key={i} style={{ marginBottom: 8 }}>{line}</div>)
        )}
      </div>
    </div>
  );
}
