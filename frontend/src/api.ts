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
export const listFolders = () => request<any[]>("/folders");
export const createFolder = (payload: { name: string; dir_name?: string; parent_id?: number | null }) =>
  request("/folders", { method: "POST", body: JSON.stringify(payload) });
export const renameFolder = (folderId: number, payload: { name: string; dir_name?: string }) =>
  request(`/folders/${folderId}/rename`, { method: "POST", body: JSON.stringify(payload) });
export const deleteFolder = (folderId: number) => request(`/folders/${folderId}`, { method: "DELETE" });

export const listSessions = (folderId?: number | null) => {
  const qs = folderId ? `?folder_id=${encodeURIComponent(String(folderId))}` : "";
  return request<any[]>(`/sessions${qs}`);
};
export const getSession = (sessionId: string) => request<any>(`/sessions/${encodeURIComponent(sessionId)}`);
export const getTranscript = (sessionId: string) =>
  request<{ session_id: string; text: string; structured?: string; title?: string; participants?: any[]; calendar?: any; assets?: any }>(
    `/sessions/${encodeURIComponent(sessionId)}/transcript`
  );
export const renameSession = (sessionId: string, title: string) =>
  request(`/sessions/${encodeURIComponent(sessionId)}/rename`, { method: "POST", body: JSON.stringify({ title }) });
export const moveSession = (sessionId: string, folderId: number) =>
  request(`/sessions/${encodeURIComponent(sessionId)}/move`, { method: "POST", body: JSON.stringify({ folder_id: folderId }) });
export const search = (payload: { prompt: string; threshold?: number }) =>
  request<{ results: any[] }>("/search", { method: "POST", body: JSON.stringify(payload) });
export const uploadFile = async (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as { session_id: string };
};
export const transcribeSession = (sessionId: string, language?: string) =>
  request<{ session_id: string; transcript_path: string; embedding_path?: string; summary_path?: string }>(`/sessions/${encodeURIComponent(sessionId)}/transcribe`, {
    method: "POST",
    body: JSON.stringify({ language }),
  });
export const embedSession = (sessionId: string) =>
  request<{ embedding_path: string }>(`/sessions/${encodeURIComponent(sessionId)}/embed`, { method: "POST" });
export const updateSpeakers = (sessionId: string, updates: Record<string, string>) =>
  request(`/sessions/${encodeURIComponent(sessionId)}/speakers`, { method: "POST", body: JSON.stringify({ updates }) });
export const generateSummary = (sessionId: string, force = false) =>
  request<{ summary: string }>(`/sessions/${encodeURIComponent(sessionId)}/summarize`, { method: "POST", body: JSON.stringify({ force }) });

export const listFolderSuggestions = () => request<any[]>("/folder_suggestions");
export const reconcileLibrary = () => request<any>("/library/reconcile", { method: "POST" });

export const calendarSuggestions = (sessionId: string, limit = 5) =>
  request<{ session_id: string; suggestions: any[] }>(`/calendar/suggestions?session_id=${encodeURIComponent(sessionId)}&limit=${encodeURIComponent(String(limit))}`);
export const linkCalendarEvent = (sessionId: string, event: any, applyParticipants = true) =>
  request(`/sessions/${encodeURIComponent(sessionId)}/calendar_link`, { method: "POST", body: JSON.stringify({ event, apply_participants: applyParticipants }) });
export const suggestTitle = (sessionId: string) =>
  request<{ titles: string[] }>(`/sessions/${encodeURIComponent(sessionId)}/suggest_title`, { method: "POST" });
