import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { listSessions, transcribeAudio, embedTranscript } from "../api";

function formatDate(ts?: string) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function SessionsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["sessions"], queryFn: listSessions });

  const processMutation = useMutation({
    mutationFn: async (audioPath: string) => {
      const t = await transcribeAudio(audioPath);
      await embedTranscript(t.transcript_path);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      alert("Processing complete.");
    },
    onError: (err: any) => alert("Processing failed: " + err.message)
  });

  if (isLoading) return <p>Loading sessions…</p>;
  if (error) return <p>Error loading sessions.</p>;

  return (
    <div className="card">
      <h2>Sessions</h2>
      <table className="table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Date</th>
            <th>Tags</th>
            <th>Transcript</th>
            <th>Embedding</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {(data || []).map((s: any) => (
            <tr key={s.id || s.audio_path}>
              <td>{s.title || "Untitled"}</td>
              <td>{formatDate(s.timestamp)}</td>
              <td>{s.tags}</td>
              <td>{s.transcript_path ? "✅" : "—"}</td>
              <td>{s.embedding_path ? "✅" : "—"}</td>
              <td>
                {s.transcript_path ? (
                  <Link to={`/sessions/${encodeURIComponent(s.transcript_path)}`}>Open</Link>
                ) : (
                  <button 
                    className="btn secondary" 
                    style={{ padding: "2px 8px", fontSize: 12 }}
                    onClick={() => processMutation.mutate(s.audio_path)}
                    disabled={processMutation.isPending}
                  >
                    {processMutation.isPending ? "..." : "Process"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
