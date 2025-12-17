import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listSessions } from "../api";

export default function Dashboard() {
  const { data: sessions } = useQuery({ queryKey: ["sessions"], queryFn: listSessions });
  const recent = sessions?.slice(0, 5) || [];

  return (
    <div>
      <div className="card" style={{ background: "linear-gradient(120deg, #15243a, #0f1724)", borderColor: "#23324a" }}>
        <h2 style={{ marginTop: 0 }}>Start a transcription</h2>
        <p style={{ color: "#9ca3af" }}>Upload or record audio, then we’ll diarize, transcribe, and embed automatically.</p>
        <div className="row">
          <Link className="btn" to="/upload">
            New transcription
          </Link>
          <Link className="btn secondary" to="/upload?record=1">
            Start recording
          </Link>
          <Link className="btn secondary" to="/sessions">
            View sessions
          </Link>
        </div>
      </div>

      <div className="card">
        <h2>Quick Actions</h2>
        <div className="row">
          <Link className="btn" to="/upload">
            Upload & Transcribe
          </Link>
          <Link className="btn secondary" to="/search">
            Search
          </Link>
          <Link className="btn secondary" to="/settings">
            Settings
          </Link>
        </div>
      </div>
      <div className="card">
        <h2>Recent Sessions</h2>
        {recent.length === 0 ? (
          <p>No sessions yet.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Date</th>
                <th>Transcript</th>
                <th>Embedding</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((s: any) => (
                <tr key={s.id || s.audio_path}>
                  <td>{s.title || "Untitled"}</td>
                  <td>{s.timestamp?.split("T")[0]}</td>
                  <td>{s.transcript_path ? "✅" : "—"}</td>
                  <td>{s.embedding_path ? "✅" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <Link to="/sessions">View all sessions →</Link>
      </div>
    </div>
  );
}
