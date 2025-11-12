// web/src/components/AgentAskRunbook.tsx
import React, { useState } from "react";

// Safe API base detection (no TS errors even if vite/client types are missing)
const API: string =
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  (((import.meta as any)?.env || {})?.VITE_API_BASE as string) ||
  "http://localhost:8000";

type AgentReply = {
  reply: string;
  confidence?: number;
  reasoning_summary?: string;
  related_entities?: any[];
  suggested_actions?: any[];
};

export default function AgentAskRunbook() {
  const [entity, setEntity] = useState("order-service");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>("");
  const [reply, setReply] = useState<AgentReply | null>(null);

  async function ask() {
    setBusy(true);
    setErr("");
    setReply(null);
    try {
      const r = await fetch(`${API}/agent/query`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: `what should we do for ${entity}?` }),
      });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = (await r.json()) as AgentReply;
      setReply(data);
    } catch (e: any) {
      setErr(e?.message || "Agent error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ marginTop: 16 }}>
      <h3>Ask Copilot for a Runbook</h3>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          placeholder="entity e.g., order-service"
          style={{ flex: 1, padding: 8 }}
        />
        <button onClick={ask} disabled={busy} style={{ padding: "8px 12px" }}>
          {busy ? "Asking..." : "Ask"}
        </button>
      </div>

      {err && (
        <div style={{ color: "tomato", marginTop: 8 }}>Error: {err}</div>
      )}

      {reply && (
        <div style={{ marginTop: 12 }}>
          <div
            style={{
              padding: 12,
              border: "1px solid #444",
              borderRadius: 8,
              background: "#121212",
            }}
          >
            <p style={{ margin: 0 }}>{reply.reply}</p>
            {reply.confidence != null && (
              <p style={{ opacity: 0.8, marginTop: 8 }}>
                Confidence: {(reply.confidence * 100).toFixed(0)}%
              </p>
            )}
            <details style={{ marginTop: 8 }}>
              <summary>Show reasoning</summary>
              <pre style={{ whiteSpace: "pre-wrap" }}>
                {JSON.stringify(reply, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}
    </section>
  );
}
