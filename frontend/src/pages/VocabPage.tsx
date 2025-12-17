import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getVocab, saveVocab } from "../api";

export default function VocabPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["vocab"], queryFn: getVocab });
  const [text, setText] = useState("");
  const mutation = useMutation({
    mutationFn: (words: string[]) => saveVocab(words),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vocab"] });
      alert("Vocabulary saved.");
    },
    onError: (err: any) => alert(err.message || "Save failed")
  });

  if (isLoading) return <p>Loading vocab…</p>;
  if (error) return <p>Error loading vocab.</p>;

  const words = text ? text.split("\n").map((w) => w.trim()).filter(Boolean) : data?.words || [];

  return (
    <div className="card">
      <h2>Custom Vocabulary</h2>
      <p>Add one term per line.</p>
      <textarea
        className="textarea"
        style={{ minHeight: 260 }}
        value={text || (data?.words || []).join("\n")}
        onChange={(e) => setText(e.target.value)}
      />
      <button className="btn" style={{ marginTop: 10 }} onClick={() => mutation.mutate(words)}>
        Save Vocabulary
      </button>
    </div>
  );
}
