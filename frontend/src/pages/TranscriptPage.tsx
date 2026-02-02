import { useMemo, useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { calendarSuggestions, getTranscript, linkCalendarEvent, suggestTitle, updateSpeakers, generateSummary, renameSession } from "../api";
import { useAudio } from "../hooks/useAudio";

type Segment = { speaker: string; text: string; start?: number; end?: number };

export default function TranscriptPage() {
  const { sessionId } = useParams();
  const id = sessionId ? decodeURIComponent(sessionId) : "";
  const qc = useQueryClient();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ["transcript", id],
    queryFn: () => getTranscript(id),
    enabled: !!id
  });
  
  const [speed, setSpeed] = useState(1);
  const { play, stop, status, error: playErr } = useAudio();
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [newSpeakerName, setNewSpeakerName] = useState("");
  const [showSummary, setShowSummary] = useState(false);
  const [summaryText, setSummaryText] = useState<string | null>(null);
  
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [title, setTitle] = useState("");
  const [titleCandidates, setTitleCandidates] = useState<string[] | null>(null);
  const [calendarCandidates, setCalendarCandidates] = useState<any[] | null>(null);

  useEffect(() => {
    if (data?.title) setTitle(data.title);
  }, [data?.title]);

  const renameMutation = useMutation({
    mutationFn: (updates: Record<string, string>) => updateSpeakers(id, updates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transcript", id] });
      setEditingSpeaker(null);
    },
    onError: (err: any) => alert("Failed to rename speaker: " + err.message)
  });

  const summaryMutation = useMutation({
    mutationFn: () => generateSummary(id),
    onSuccess: (data) => {
      setSummaryText(data.summary);
      setShowSummary(true);
    },
    onError: (err: any) => alert("Failed to generate summary: " + err.message)
  });

  const titleMutation = useMutation({
    mutationFn: (newTitle: string) => renameSession(id, newTitle),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transcript", id] });
      setIsEditingTitle(false);
    },
    onError: (err: any) => alert("Failed to rename session: " + err.message)
  });

  const suggestTitleMutation = useMutation({
    mutationFn: () => suggestTitle(id),
    onSuccess: (res) => setTitleCandidates(res.titles || []),
    onError: (err: any) => alert("Title suggestion failed: " + err.message),
  });

  const calendarMutation = useMutation({
    mutationFn: () => calendarSuggestions(id, 5),
    onSuccess: (res) => setCalendarCandidates(res.suggestions || []),
    onError: (err: any) => alert("Calendar fetch failed: " + err.message),
  });

  const calendarLinkMutation = useMutation({
    mutationFn: (event: any) => linkCalendarEvent(id, event, true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["transcript", id] });
      setCalendarCandidates(null);
    },
    onError: (err: any) => alert("Linking event failed: " + err.message),
  });

  const handleRename = (oldName: string) => {
    if (!newSpeakerName.trim() || newSpeakerName === oldName) {
      setEditingSpeaker(null);
      return;
    }
    renameMutation.mutate({ [oldName]: newSpeakerName.trim() });
  };

  const handleTitleSave = () => {
    if (title.trim()) titleMutation.mutate(title.trim());
    else setIsEditingTitle(false);
  };

  const downloadTranscript = (format: "txt" | "json") => {
    if (!data) return;
    let content = "";
    let mime = "text/plain";
    let ext = "txt";

    if (format === "json") {
      content = data.structured || JSON.stringify({ text: data.text }, null, 2);
      mime = "application/json";
      ext = "json";
    } else {
      content = data.text;
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.replace(/[^a-z0-9]/gi, "_")}_transcript.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const segments: Segment[] = useMemo(() => {
    if (!data) return [];
    if (data.structured) {
      try {
        const parsed = JSON.parse(data.structured);
        return (parsed.segments || []).map((s: any) => ({
          speaker: s.speaker || "Unknown",
          text: s.text || "",
          start: s.start,
          end: s.end
        }));
      } catch {
        // ignore
      }
    }
    return data.text
      .split("\n")
      .filter(Boolean)
      .map((line) => {
        if (line.startsWith("[") && line.includes("]")) {
          const speaker = line.slice(1, line.indexOf("]"));
          return { speaker, text: line.slice(line.indexOf("]") + 1).trim() };
        }
        return { speaker: "Unknown", text: line };
      });
  }, [data]);

  const audioSrc = (start?: number, end?: number) =>
    `/sessions/${encodeURIComponent(id)}/audio?start=${start || 0}&end=${end || 0}`;

  if (isLoading) return <p>Loading transcript…</p>;
  if (error) return <p>Error loading transcript.</p>;
  if (!data) return <p>Not found.</p>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          {isEditingTitle ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input 
                className="input" 
                value={title} 
                onChange={(e) => setTitle(e.target.value)}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTitleSave();
                  if (e.key === "Escape") setIsEditingTitle(false);
                }}
              />
              <button className="btn" onClick={handleTitleSave}>Save</button>
              <button className="btn secondary" onClick={() => setIsEditingTitle(false)}>Cancel</button>
            </div>
          ) : (
            <h2 
              style={{ margin: 0, cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }} 
              onClick={() => setIsEditingTitle(true)}
              title="Click to rename"
            >
              {title || "Transcript"} 
              <span style={{ fontSize: 12, opacity: 0.5 }}>✎</span>
            </h2>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn secondary"
            onClick={() => suggestTitleMutation.mutate()}
            disabled={suggestTitleMutation.isPending}
          >
            {suggestTitleMutation.isPending ? "Suggesting..." : "Suggest Title"}
          </button>
          <button className="btn secondary" onClick={() => downloadTranscript("txt")}>Download TXT</button>
          <button className="btn secondary" onClick={() => downloadTranscript("json")}>Download JSON</button>
          <button 
            className="btn secondary" 
            onClick={() => {
              if (summaryText) setShowSummary(!showSummary);
              else summaryMutation.mutate();
            }}
            disabled={summaryMutation.isPending}
          >
            {summaryMutation.isPending ? "Generating Summary..." : (summaryText ? (showSummary ? "Hide Summary" : "Show Summary") : "Generate Summary")}
          </button>
        </div>
      </div>

      {titleCandidates && titleCandidates.length > 0 && (
        <div className="card" style={{ background: "#11151c", marginBottom: 16 }}>
          <h3 style={{ marginTop: 0 }}>Suggested titles</h3>
          <div style={{ display: "grid", gap: 8 }}>
            {titleCandidates.map((t) => (
              <div key={t} style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                <div style={{ flex: 1 }}>{t}</div>
                <button className="btn secondary" onClick={() => titleMutation.mutate(t)}>
                  Apply
                </button>
              </div>
            ))}
          </div>
          <button className="btn secondary" style={{ marginTop: 10 }} onClick={() => setTitleCandidates(null)}>
            Dismiss
          </button>
        </div>
      )}

      <div className="card" style={{ background: "#11151c", marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ marginTop: 0, marginBottom: 0 }}>Calendar</h3>
          <button className="btn secondary" onClick={() => calendarMutation.mutate()} disabled={calendarMutation.isPending}>
            {calendarMutation.isPending ? "Loading..." : "Suggest Event"}
          </button>
        </div>
        {data.calendar ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontWeight: 600 }}>{data.calendar.summary || "(no title)"}</div>
            <div style={{ opacity: 0.7, fontSize: 13 }}>{data.calendar.start} → {data.calendar.end}</div>
          </div>
        ) : (
          <div style={{ marginTop: 8, opacity: 0.7 }}>No event linked.</div>
        )}
        {Array.isArray(data.participants) && data.participants.length > 0 && (
          <div style={{ marginTop: 10, opacity: 0.9, fontSize: 13 }}>
            Participants: {data.participants.map((p: any) => p.name || p.email || String(p)).join(", ")}
          </div>
        )}
        {calendarCandidates && (
          <div style={{ marginTop: 12 }}>
            <h4 style={{ margin: "8px 0" }}>Suggestions</h4>
            {calendarCandidates.length === 0 ? (
              <div style={{ opacity: 0.7 }}>No nearby events found.</div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {calendarCandidates.map((ev: any) => (
                  <div key={ev.uid} className="card" style={{ background: "#0f131b", borderColor: "#1d2431" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600 }}>{ev.summary}</div>
                        <div style={{ opacity: 0.7, fontSize: 12 }}>{ev.start} → {ev.end}</div>
                        {typeof ev.score === "number" && (
                          <div style={{ opacity: 0.6, fontSize: 12 }}>score {ev.score.toFixed(3)}</div>
                        )}
                      </div>
                      <button className="btn secondary" onClick={() => calendarLinkMutation.mutate(ev)} disabled={calendarLinkMutation.isPending}>
                        Attach
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button className="btn secondary" style={{ marginTop: 10 }} onClick={() => setCalendarCandidates(null)}>
              Close
            </button>
          </div>
        )}
      </div>

      {showSummary && summaryText && (
        <div className="card" style={{ background: "#171c24", marginBottom: 16, whiteSpace: "pre-wrap" }}>
          <h3>Meeting Summary</h3>
          {summaryText}
        </div>
      )}

      <div className="row" style={{ marginBottom: 10 }}>
        <div>Speed</div>
        <select className="select" style={{ width: 120 }} value={speed} onChange={(e) => setSpeed(parseFloat(e.target.value))}>
          {[0.5, 1, 1.5, 2, 3].map((r) => (
            <option key={r} value={r}>
              {r}×
            </option>
          ))}
        </select>
        <div>Status: {status}</div>
        {playErr && <div style={{ color: "#f87171" }}>{playErr}</div>}
        <button className="btn secondary" onClick={() => stop()}>
          Stop
        </button>
      </div>
      <div style={{ maxHeight: "70vh", overflow: "auto" }}>
        {segments.map((s, idx) => (
          <div key={idx} style={{ padding: "8px 0", borderBottom: "1px solid #1f2530" }}>
            <div style={{ fontSize: 12, color: "#9ca3af", display: "flex", alignItems: "center", gap: 8 }}>
              <span>[{s.start?.toFixed(1) ?? "—"} - {s.end?.toFixed(1) ?? "—"}]</span>
              
              {editingSpeaker === s.speaker ? (
                <div style={{ display: "flex", gap: 4 }}>
                  <input 
                    className="input" 
                    style={{ padding: "2px 4px", fontSize: 12, width: 100 }} 
                    value={newSpeakerName} 
                    onChange={(e) => setNewSpeakerName(e.target.value)}
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleRename(s.speaker);
                      if (e.key === "Escape") setEditingSpeaker(null);
                    }}
                  />
                  <button className="btn" style={{ padding: "2px 6px", fontSize: 10 }} onClick={() => handleRename(s.speaker)}>✓</button>
                  <button className="btn secondary" style={{ padding: "2px 6px", fontSize: 10 }} onClick={() => setEditingSpeaker(null)}>✕</button>
                </div>
              ) : (
                <span 
                  style={{ cursor: "pointer", textDecoration: "underline", textDecorationStyle: "dotted" }}
                  onClick={() => {
                    setEditingSpeaker(s.speaker);
                    setNewSpeakerName(s.speaker);
                  }}
                  title="Click to rename speaker"
                >
                  {s.speaker}
                </span>
              )}
            </div>
            <div style={{ margin: "4px 0" }}>{s.text}</div>
            <button className="btn secondary" onClick={() => play(audioSrc(s.start, s.end), speed)}>
              Play
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
