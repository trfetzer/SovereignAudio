import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSettings, saveSettings } from "../api";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const [form, setForm] = useState<any | null>(null);
  const mutation = useMutation({
    mutationFn: saveSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      alert("Settings saved.");
    },
    onError: (err: any) => alert(err.message || "Save failed"),
  });

  const current = form || data;
  const update = (k: string, v: any) => setForm({ ...(current || {}), [k]: v });

  if (isLoading) return <p>Loading settings…</p>;
  if (error) return <p>Error loading settings.</p>;

  return (
    <div className="card">
      <h2>Settings</h2>
      <p style={{ color: "#9ca3af", marginTop: 0 }}>Control the models and automation used by the backend.</p>
      <div className="row">
        <div style={{ flex: 1, minWidth: 240 }}>
          <label>ASR Model</label>
          <input className="input" value={current?.asr_model || ""} onChange={(e) => update("asr_model", e.target.value)} />
        </div>
        <div style={{ width: 180 }}>
          <label>Language</label>
          <input className="input" value={current?.language || ""} onChange={(e) => update("language", e.target.value)} />
        </div>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <div style={{ flex: 1, minWidth: 240 }}>
          <label>Embedding Model (doc)</label>
          <input className="input" value={current?.embed_model_doc || ""} onChange={(e) => update("embed_model_doc", e.target.value)} />
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          <label>Embedding Model (query)</label>
          <input className="input" value={current?.embed_model_query || ""} onChange={(e) => update("embed_model_query", e.target.value)} />
        </div>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <div style={{ flex: 1, minWidth: 240 }}>
          <label>Summary Model (Ollama)</label>
          <input className="input" value={current?.summary_model || ""} onChange={(e) => update("summary_model", e.target.value)} placeholder="e.g. llama3:latest" />
        </div>
        <div style={{ flex: 1, minWidth: 240 }}>
          <label>Title Model (optional)</label>
          <input
            className="input"
            value={current?.title_model || ""}
            onChange={(e) => update("title_model", e.target.value)}
            placeholder="defaults to Summary Model"
          />
        </div>
      </div>

      <div className="row" style={{ marginTop: 16, gap: 16 }}>
        <label className="toggle">
          <input
            type="checkbox"
            checked={Boolean(current?.auto_embed)}
            onChange={(e) => update("auto_embed", e.target.checked)}
          />
          <span className="toggle-label">
            Auto-embed after transcription
            <span className="hint">Embeds transcripts immediately to keep search ready.</span>
          </span>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={Boolean(current?.auto_summarize)}
            onChange={(e) => update("auto_summarize", e.target.checked)}
          />
          <span className="toggle-label">
            Auto-generate summaries
            <span className="hint">Creates a summary alongside each transcript.</span>
          </span>
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={Boolean(current?.auto_title_suggest)}
            onChange={(e) => update("auto_title_suggest", e.target.checked)}
          />
          <span className="toggle-label">
            Auto-suggest titles
            <span className="hint">Generates title candidates after transcription.</span>
          </span>
        </label>
      </div>

      <div className="card" style={{ marginTop: 16, background: "#11151c" }}>
        <h3 style={{ marginTop: 0 }}>Calendar (ICS feed)</h3>
        <div className="row">
          <div style={{ flex: 1, minWidth: 240 }}>
            <label>ICS URL</label>
            <input
              className="input"
              value={current?.calendar_ics_url || ""}
              onChange={(e) => update("calendar_ics_url", e.target.value)}
              placeholder="https://calendar.google.com/calendar/ical/.../public/basic.ics"
            />
          </div>
          <div style={{ width: 220 }}>
            <label>Match window (minutes)</label>
            <input
              className="input"
              type="number"
              value={current?.calendar_match_window_minutes ?? 45}
              onChange={(e) => update("calendar_match_window_minutes", parseInt(e.target.value || "45", 10))}
            />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16, background: "#11151c" }}>
        <h3 style={{ marginTop: 0 }}>Privacy</h3>
        <div className="row">
          <div style={{ flex: 1, minWidth: 240 }}>
            <label>Audio after processing</label>
            <select
              className="select"
              value={current?.audio_postprocess_action || "keep"}
              onChange={(e) => update("audio_postprocess_action", e.target.value)}
            >
              <option value="keep">Keep original audio</option>
              <option value="delete">Delete original audio</option>
              <option value="sanitize">Replace with noisy audio (sanitize)</option>
            </select>
            <div className="hint" style={{ marginTop: 6 }}>
              Deleting is the only reliable way to prevent reuse; sanitizing reduces voice fidelity but is not a formal guarantee.
            </div>
          </div>
        </div>
        {String(current?.audio_postprocess_action || "keep") === "sanitize" && (
          <div className="row" style={{ marginTop: 12 }}>
            <div style={{ width: 220 }}>
              <label>Sanitize SNR (dB)</label>
              <input
                className="input"
                type="number"
                step="0.5"
                value={current?.audio_sanitize_snr_db ?? 0}
                onChange={(e) => update("audio_sanitize_snr_db", parseFloat(e.target.value || "0"))}
              />
            </div>
            <div style={{ width: 220 }}>
              <label>Resample (Hz)</label>
              <input
                className="input"
                type="number"
                value={current?.audio_sanitize_resample_hz ?? 8000}
                onChange={(e) => update("audio_sanitize_resample_hz", parseInt(e.target.value || "8000", 10))}
              />
            </div>
          </div>
        )}
      </div>

      <button className="btn" style={{ marginTop: 18 }} onClick={() => mutation.mutate(current || {})}>
        Save
      </button>
    </div>
  );
}
