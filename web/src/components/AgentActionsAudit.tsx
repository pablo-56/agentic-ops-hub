// web/src/components/AgentActionsAudit.tsx
import React, { useEffect, useMemo, useState } from "react";

const API: string =
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  (((import.meta as any)?.env || {})?.VITE_API_BASE as string) ||
  "http://localhost:8000";

type AuditRow = {
  action_id: string;
  runbook_id?: string | null;
  action_type?: string | null;
  incident_id?: string | null;
  entity_id?: string | null;
  status?: string | null;
  triggered_by?: string | null;
  approved_by?: string | null;
  reasoning?: string | null;
  created_at?: string | null;
};

async function fetchJSON<T = any>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

export default function AgentActionsAudit() {
  const [status, setStatus] = useState<string>("all");
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const url = useMemo(() => {
    const base = `${API}/runbooks/agent-actions`;
    return status === "all" ? base : `${base}?status=${encodeURIComponent(status)}`;
  }, [status]);

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const data: any = await fetchJSON(url);
      setRows((data?.items as AuditRow[]) ?? (Array.isArray(data) ? data : []));
    } catch (e: any) {
      setErr(e.message || "Failed to load agent actions");
      setRows([]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 7000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return (
    <section style={{ marginTop: 24 }}>
      <h3>Agent Actions Audit Log</h3>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <label>Status:</label>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="all">All</option>
          <option value="pending_approval">pending_approval</option>
          <option value="executed">executed</option>
          <option value="rejected">rejected</option>
        </select>
        <button onClick={load} disabled={busy} style={{ marginLeft: "auto" }}>
          {busy ? "Loading..." : "Refresh"}
        </button>
      </div>

      {err && <div style={{ color: "tomato", marginBottom: 8 }}>Error: {err}</div>}

      {rows.length === 0 ? (
        <p>No items.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 8 }}>When</th>
                <th style={{ textAlign: "left", padding: 8 }}>Action ID</th>
                <th style={{ textAlign: "left", padding: 8 }}>Runbook</th>
                <th style={{ textAlign: "left", padding: 8 }}>Entity</th>
                <th style={{ textAlign: "left", padding: 8 }}>Status</th>
                <th style={{ textAlign: "left", padding: 8 }}>By</th>
                <th style={{ textAlign: "left", padding: 8 }}>Approved</th>
                <th style={{ textAlign: "left", padding: 8 }}>Reasoning</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.action_id} style={{ borderTop: "1px solid #444" }}>
                  <td style={{ padding: 8 }}>{r.created_at || "-"}</td>
                  <td style={{ padding: 8, fontFamily: "monospace" }}>{r.action_id}</td>
                  <td style={{ padding: 8 }}>{r.runbook_id || "-"}</td>
                  <td style={{ padding: 8 }}>{r.entity_id || "-"}</td>
                  <td style={{ padding: 8 }}>{r.status || "-"}</td>
                  <td style={{ padding: 8 }}>{r.triggered_by || "-"}</td>
                  <td style={{ padding: 8 }}>{r.approved_by || "-"}</td>
                  <td style={{ padding: 8, maxWidth: 400, whiteSpace: "pre-wrap" }}>
                    {r.reasoning || "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
