import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { search } from "../api";
import { useAudio } from "../hooks/useAudio";

export default function SearchPage() {
  const [prompt, setPrompt] = useState("");
  const [threshold, setThreshold] = useState(0.75);
  const [results, setResults] = useState<any[]>([]);
  const { play, rate, changeRate, error, status } = useAudio();

  const mutation = useMutation({
    mutationFn: search,
    onSuccess: (data) => setResults(data.results || []),
    onError: (err: any) => alert(err.message || "Search failed")
  });

  const handleSearch = () => {
    if (!prompt.trim()) return;
    mutation.mutate({ prompt, threshold });
  };

  return (
    <div>
      <div className="card">
        <h2>Semantic Search</h2>
        <textarea className="textarea" value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Enter query" />
        <div className="row" style={{ marginTop: 8 }}>
          <div>
            <label>Threshold</label>
            <input className="input" type="number" step="0.01" value={threshold} onChange={(e) => setThreshold(parseFloat(e.target.value))} style={{ width: 120 }} />
          </div>
          <div>
            <label>Playback speed</label>
            <select className="select" value={rate} onChange={(e) => changeRate(parseFloat(e.target.value))} style={{ width: 120 }}>
              {[0.5, 1, 1.5, 2, 3].map((r) => (
                <option key={r} value={r}>
                  {r}×
                </option>
              ))}
            </select>
          </div>
          <button className="btn" onClick={handleSearch} disabled={mutation.isPending}>
            {mutation.isPending ? "Searching..." : "Search"}
          </button>
          <button className="btn secondary" onClick={() => setResults([])}>
            Clear
          </button>
        </div>
        {error && <div style={{ color: "#f87171" }}>{error}</div>}
        <div>Status: {status}</div>
      </div>
      <div className="card">
        <h3>Results ({results.length})</h3>
        {results.length === 0 && <p>No results.</p>}
        <div style={{ maxHeight: "70vh", overflow: "auto" }}>
          {results.map((r, idx) => {
            const start = r.start || 0;
            const end = r.end || 0;
            const url = r.transcript_path ? `/audio?transcript_path=${encodeURIComponent(r.transcript_path)}&start=${start}&end=${end}` : "";
            return (
              <div key={idx} style={{ padding: "8px 0", borderBottom: "1px solid #1f2530" }}>
                <div style={{ fontSize: 12, color: "#9ca3af" }}>
                  {r.kind} • sim {r.similarity?.toFixed ? r.similarity.toFixed(3) : r.similarity} • {r.session_path}
                </div>
                <div style={{ margin: "6px 0" }}>{r.snippet || r.text}</div>
                <div className="row">
                  <button className="btn secondary" disabled={!url} onClick={() => play(url, rate)}>
                    Play segment
                  </button>
                  {r.transcript_path && (
                    <a className="btn secondary" href={`/sessions/${encodeURIComponent(r.transcript_path)}`}>
                      Open transcript
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
