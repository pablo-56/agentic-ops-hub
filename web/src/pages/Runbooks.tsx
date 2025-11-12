// web/src/pages/Runbooks.tsx
import React, { useEffect, useState } from "react";
import AgentAskRunbook from "../components/AgentAskRunbook";
import ProposedActions from "../components/ProposedActions";
import AgentActionsAudit from "../components/AgentActionsAudit";

// Safe API base detection (works even if vite types/env aren't configured)
const API: string =
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  (((import.meta as any)?.env || {})?.VITE_API_BASE as string) ||
  "http://localhost:8000";

type Runbook = {
  runbook_id: string;
  name: string;
  description?: string;
  risk_level?: string;
  enabled?: boolean;
};

export default function Runbooks() {
  const [list, setList] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`${API}/runbooks`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const data = await r.json();
      const items = (Array.isArray(data) ? data : data?.items) || [];
      setList(items);
    } catch (e: any) {
      setErr(e.message || "Failed to load runbooks");
      setList([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main style={{ padding: 16 }}>
      <h1>Playbook Center</h1>

      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button onClick={load} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </button>
        {err && <span style={{ color: "tomato" }}>Error: {err}</span>}
      </div>

      <h3 style={{ marginTop: 12 }}>Available Runbooks</h3>
      {list.length === 0 ? (
        <p>No runbooks yet.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 8 }}>ID</th>
                <th style={{ textAlign: "left", padding: 8 }}>Name</th>
                <th style={{ textAlign: "left", padding: 8 }}>Risk</th>
                <th style={{ textAlign: "left", padding: 8 }}>Enabled</th>
                <th style={{ textAlign: "left", padding: 8 }}>Description</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.runbook_id} style={{ borderTop: "1px solid #444" }}>
                  <td style={{ padding: 8, fontFamily: "monospace" }}>{r.runbook_id}</td>
                  <td style={{ padding: 8 }}>{r.name}</td>
                  <td style={{ padding: 8 }}>{r.risk_level || "-"}</td>
                  <td style={{ padding: 8 }}>{String(r.enabled ?? true)}</td>
                  <td style={{ padding: 8 }}>{r.description || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Ask the agent → creates proposed actions (pending_approval) */}
      <AgentAskRunbook />

      {/* Approve & execute */}
      <ProposedActions />

      {/* Audit log */}
      <AgentActionsAudit />
    </main>
  );
}
