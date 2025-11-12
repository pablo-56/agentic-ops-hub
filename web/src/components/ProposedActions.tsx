// web/src/components/ProposedActions.tsx
import React, { useCallback, useEffect, useState } from "react";

const API: string =
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  (((import.meta as any)?.env || {})?.VITE_API_BASE as string) ||
  "http://localhost:8000";

type AgentAction = {
  action_id: string;
  runbook_id: string;
  action_type: string;
  incident_id?: string | null;
  entity_id: string;
  status: string;
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

async function resolveEntityTypeBySearch(eid: string): Promise<string | null> {
  try {
    const res: any = await fetchJSON(`${API}/graph/search?q=${encodeURIComponent(eid)}`);
    const results = Array.isArray(res?.results) ? res.results : [];
    if (!results.length) return null;

    // Find best match by id/name/title
    const hit =
      results.find((r: any) => {
        const p = r?.props || {};
        return p?.id === eid || p?.name === eid || p?.title === eid;
      }) || results[0];

    const labels: string[] = hit?.labels || [];
    for (const t of [
      "Service",
      "Database",
      "API",
      "Server",
      "Topic",
      "Machine",
      "Line",
      "Plant",
      "Sensor",
      "Team",
    ]) {
      if (labels.includes(t)) return t;
    }
    return labels[0] ?? null;
  } catch {
    return null;
  }
}

export default function ProposedActions() {
  const [rows, setRows] = useState<AgentAction[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState<string>("");

  const load = useCallback(async () => {
    try {
      setErr("");
      // Your backend returns either {items: [...]} or plain array; support both.
      const data: any = await fetchJSON(`${API}/runbooks/agent-actions?status=pending_approval`);
      setRows((data?.items as AgentAction[]) ?? (Array.isArray(data) ? data : []));
    } catch (e: any) {
      setErr(e.message || "Failed to load proposed actions");
      setRows([]);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const approve = async (row: AgentAction) => {
    try {
      setBusyId(row.action_id);
      setErr("");

      const entityType = (await resolveEntityTypeBySearch(row.entity_id)) || "Service";
      const targets = [{ entity_type: entityType, entity_id: row.entity_id }];

      const r = await fetch(
        `${API}/runbooks/${encodeURIComponent(row.runbook_id)}/execute?mode=execute`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            targets,
            reason: `Approved action ${row.action_id} from UI`,
          }),
        }
      );
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`Execute failed: ${r.status} ${txt}`);
      }
      await load();
    } catch (e: any) {
      setErr(e.message || "Approval failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section style={{ marginTop: 24 }}>
      <h3>Proposed Actions (need approval)</h3>
      {err && <div style={{ color: "tomato", marginBottom: 8 }}>Error: {err}</div>}
      {rows.length === 0 ? (
        <p>No proposed actions awaiting approval.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left", padding: 8 }}>Action ID</th>
                <th style={{ textAlign: "left", padding: 8 }}>Runbook</th>
                <th style={{ textAlign: "left", padding: 8 }}>Entity</th>
                <th style={{ textAlign: "left", padding: 8 }}>Reasoning</th>
                <th style={{ textAlign: "left", padding: 8 }}>Created</th>
                <th style={{ padding: 8 }}>Approve</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.action_id} style={{ borderTop: "1px solid #444" }}>
                  <td style={{ padding: 8, fontFamily: "monospace" }}>{r.action_id}</td>
                  <td style={{ padding: 8 }}>{r.runbook_id}</td>
                  <td style={{ padding: 8 }}>{r.entity_id}</td>
                  <td style={{ padding: 8 }}>{r.reasoning || "-"}</td>
                  <td style={{ padding: 8 }}>{r.created_at || "-"}</td>
                  <td style={{ padding: 8, whiteSpace: "nowrap" }}>
                    <button
                      disabled={busyId === r.action_id}
                      onClick={() => approve(r)}
                      style={{ padding: "6px 10px" }}
                    >
                      {busyId === r.action_id ? "Approving..." : "Approve & Execute"}
                    </button>
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
