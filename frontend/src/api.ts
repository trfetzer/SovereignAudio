export const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": opts.body instanceof FormData ? undefined : "application/json",
      ...(opts.headers || {})
    },
    ...opts
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json() as Promise<T>;
  return (await res.text()) as unknown as T;
}

export const getSettings = () => request("/settings");
export const saveSettings = (payload: Record<string, unknown>) => request("/settings", { method: "POST", body: JSON.stringify(payload) });
export const getVocab = () => request<{ words: string[] }>("/vocab");
export const saveVocab = (words: string[]) => request("/vocab", { method: "POST", body: JSON.stringify({ words }) });
export const listSessions = () => request<any[]>("/sessions");
export const getTranscript = (sessionPath: string) =>
  request<{ transcript_path: string; text: string; structured?: string; title?: string }>(`/transcripts/${encodeURIComponent(sessionPath)}`);
export const renameSession = (sessionPath: string, title: string) =>
  request(`/sessions/${encodeURIComponent(sessionPath)}/rename`, { method: "POST", body: JSON.stringify({ title }) });
export const search = (payload: { prompt: string; threshold?: number }) =>
  request<{ results: any[] }>("/search", { method: "POST", body: JSON.stringify(payload) });
export const uploadFile = async (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as { audio_path: string };
};
export const transcribeAudio = (audio_path: string, language?: string) =>
  request<{ transcript_path: string; embedding_path?: string; summary_path?: string }>("/transcribe", {
    method: "POST",
    body: JSON.stringify({ audio_path, language }),
  });
export const embedTranscript = (transcript_path: string) =>
  request<{ embedding_path: string }>("/embed", { method: "POST", body: JSON.stringify({ transcript_path }) });
export const updateSpeakers = (sessionPath: string, updates: Record<string, string>) =>
  request(`/transcripts/${encodeURIComponent(sessionPath)}/speakers`, { method: "POST", body: JSON.stringify({ updates }) });
export const generateSummary = (sessionPath: string, force = false) =>
  request<{ summary: string }>("/summarize", { method: "POST", body: JSON.stringify({ session_path: sessionPath, force }) });
