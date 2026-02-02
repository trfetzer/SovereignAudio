import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createFolder, embedSession, listFolders, listSessions, moveSession, reconcileLibrary, transcribeSession } from "../api";
import { useEffect, useMemo, useState } from "react";

function formatDate(ts?: string) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function SessionsPage() {
  const qc = useQueryClient();
  const { data: folders, isLoading: foldersLoading } = useQuery({ queryKey: ["folders"], queryFn: listFolders });
  const [selectedFolderId, setSelectedFolderId] = useState<number | null>(null); // null = all

  const inboxFolder = useMemo(() => (folders || []).find((f: any) => f.dir_name === "Inbox"), [folders]);
  const folderMap = useMemo(() => new Map((folders || []).map((f: any) => [f.id, f])), [folders]);

  useEffect(() => {
    if (selectedFolderId === null) return;
    if (selectedFolderId === undefined || selectedFolderId === -1) return;
  }, [selectedFolderId]);

  useEffect(() => {
    // Default to Inbox once folders load.
    if (foldersLoading) return;
    if (selectedFolderId !== null) return;
    if (inboxFolder?.id) setSelectedFolderId(inboxFolder.id);
  }, [foldersLoading, inboxFolder?.id, selectedFolderId]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["sessions", selectedFolderId],
    queryFn: () => listSessions(selectedFolderId),
    enabled: selectedFolderId !== undefined,
  });

  const processMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      const t = await transcribeSession(sessionId);
      if (!t.embedding_path) await embedSession(sessionId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      alert("Processing complete.");
    },
    onError: (err: any) => alert("Processing failed: " + err.message)
  });

  const moveMutation = useMutation({
    mutationFn: async (args: { sessionId: string; folderId: number }) => moveSession(args.sessionId, args.folderId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: (err: any) => alert("Move failed: " + err.message),
  });

  const reconcileMutation = useMutation({
    mutationFn: reconcileLibrary,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      qc.invalidateQueries({ queryKey: ["folders"] });
      alert("Library reconciled.");
    },
    onError: (err: any) => alert("Reconcile failed: " + err.message),
  });

  const createFolderMutation = useMutation({
    mutationFn: createFolder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["folders"] }),
    onError: (err: any) => alert("Folder create failed: " + err.message),
  });

  if (isLoading) return <p>Loading sessions…</p>;
  if (error) return <p>Error loading sessions.</p>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 16 }}>
      <div className="card" style={{ height: "fit-content" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Folders</h3>
          <button
            className="btn secondary"
            style={{ padding: "4px 8px", fontSize: 12 }}
            onClick={() => reconcileMutation.mutate()}
            disabled={reconcileMutation.isPending}
          >
            {reconcileMutation.isPending ? "…" : "Repair"}
          </button>
        </div>

        <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
          <button
            className="btn secondary"
            style={{ padding: "4px 8px", fontSize: 12 }}
            onClick={() => setSelectedFolderId(null)}
          >
            All
          </button>
          <button
            className="btn secondary"
            style={{ padding: "4px 8px", fontSize: 12 }}
            onClick={() => {
              const name = prompt("Folder name?");
              if (!name) return;
              createFolderMutation.mutate({ name });
            }}
            disabled={createFolderMutation.isPending}
          >
            + Folder
          </button>
        </div>

        <div style={{ marginTop: 12 }}>
          {(folders || []).map((f: any) => {
            const active = selectedFolderId === f.id;
            return (
              <div
                key={f.id}
                onClick={() => setSelectedFolderId(f.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const sid = e.dataTransfer.getData("text/session-id");
                  if (!sid) return;
                  moveMutation.mutate({ sessionId: sid, folderId: f.id });
                }}
                style={{
                  padding: "8px 10px",
                  borderRadius: 8,
                  cursor: "pointer",
                  background: active ? "#15243a" : "transparent",
                  border: active ? "1px solid #2a3b55" : "1px solid transparent",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  userSelect: "none",
                }}
                title="Drop sessions here to move"
              >
                <span style={{ fontWeight: 600 }}>{f.name}</span>
                <span style={{ fontSize: 12, opacity: 0.6 }}>{f.kind === "system" ? "system" : ""}</span>
              </div>
            );
          })}
        </div>
      </div>

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
              <th>Suggested Folder</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(data || []).map((s: any) => {
              const suggested = s.suggested_folder_id ? folderMap.get(s.suggested_folder_id) : null;
              return (
                <tr
                  key={s.session_id}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData("text/session-id", s.session_id)}
                  title="Drag this row onto a folder to move"
                  style={{ opacity: s.missing_on_disk ? 0.5 : 1 }}
                >
                  <td>{s.title || "Untitled"}</td>
                  <td>{formatDate(s.timestamp)}</td>
                  <td>{s.tags}</td>
                  <td>{s.transcript_path ? "✅" : "—"}</td>
                  <td>{s.embedding_path ? "✅" : "—"}</td>
                  <td>
                    {suggested ? (
                      <span>
                        {suggested.name}{" "}
                        {typeof s.suggested_folder_score === "number" ? (
                          <span style={{ opacity: 0.6, fontSize: 12 }}>({s.suggested_folder_score.toFixed(2)})</span>
                        ) : null}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    {s.suggested_folder_id ? (
                      <button
                        className="btn secondary"
                        style={{ padding: "2px 8px", fontSize: 12 }}
                        onClick={() => moveMutation.mutate({ sessionId: s.session_id, folderId: s.suggested_folder_id })}
                        disabled={moveMutation.isPending}
                      >
                        Apply
                      </button>
                    ) : null}
                    {s.transcript_path ? (
                      <Link to={`/sessions/${encodeURIComponent(s.session_id)}`}>Open</Link>
                    ) : (
                      <button
                        className="btn secondary"
                        style={{ padding: "2px 8px", fontSize: 12 }}
                        onClick={() => processMutation.mutate(s.session_id)}
                        disabled={processMutation.isPending}
                      >
                        {processMutation.isPending ? "..." : "Process"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
