// web/src/components/AgentDock.tsx
import React, { useState } from "react";

/**
 * Right-side, always-on Copilot dock.
 * - Input bound to POST /agent/query
 * - Shows text answer + confidence
 * - "Show reasoning" toggles a JSON view of details
 */
export default function AgentDock() {
  const [open, setOpen] = useState(true);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [showReason, setShowReason] = useState(false);
  const apiBase = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

  async function ask(e?: React.FormEvent) {
    e?.preventDefault();
    if (!msg.trim()) return;
    setBusy(true);
    setShowReason(false);
    try {
      const r = await fetch(`${apiBase}/agent/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      const j = await r.json();
      setResp(j);
    } catch (err) {
      setResp({ reply: String(err), confidence: 0.0, reasoning_summary: "Client error" });
    } finally {
      setBusy(false);
    }
  }


  
  const styles: React.CSSProperties = {
    position: "fixed",
    top: 16,
    right: 16,
    width: open ? 360 : 42,
    height: open ? 520 : 42,
    background: "#0f172a",
    color: "#e2e8f0",
    border: "1px solid #334155",
    borderRadius: 12,
    boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
    overflow: "hidden",
    transition: "all .2s ease-in-out",
    zIndex: 50,
  };

  return (
    <aside style={styles}>
      <header style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", borderBottom: "1px solid #1f2937" }}>
        <button
          onClick={() => setOpen(!open)}
          title={open ? "Collapse" : "Open Copilot"}
          style={{ border: "none", background: "transparent", color: "#93c5fd", cursor: "pointer", fontSize: 18 }}
        >
          {open ? "⮜" : "🤖"}
        </button>
        {open && <strong style={{ fontSize: 14 }}>Ops Copilot</strong>}
        <div style={{ marginLeft: "auto", fontSize: 12, opacity: 0.6 }}>v3</div>
      </header>

      {open && (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100% - 44px)" }}>
          <div style={{ padding: 12, borderBottom: "1px solid #1f2937" }}>
            <form onSubmit={ask} style={{ display: "flex", gap: 8 }}>
              <input
                value={msg}
                onChange={(e) => setMsg(e.target.value)}
                placeholder='Try: "incidents last 2h" or "why is service order-service slow"'
                style={{ flex: 1, padding: "8px 10px", background: "#0b1220", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 8 }}
              />
              <button
                disabled={busy}
                style={{
                  padding: "8px 12px",
                  background: busy ? "#1f2937" : "#2563eb",
                  color: "#fff",
                  borderRadius: 8,
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Ask
              </button>
            </form>
          </div>

          <div style={{ padding: 12, overflow: "auto", flex: 1 }}>
            {resp ? (
              <>
                <div style={{ marginBottom: 10, lineHeight: 1.4 }}>{resp.reply}</div>
                <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
                  confidence: {(Number(resp.confidence || 0) * 100).toFixed(0)}% · {resp.reasoning_summary}
                </div>
                <button
                  onClick={() => setShowReason((v) => !v)}
                  style={{ fontSize: 12, background: "transparent", color: "#93c5fd", border: "none", cursor: "pointer" }}
                >
                  {showReason ? "Hide" : "Show"} reasoning
                </button>
                {showReason && (
                  <pre
                    style={{
                      marginTop: 8,
                      background: "#0b1220",
                      border: "1px solid #334155",
                      borderRadius: 8,
                      padding: 8,
                      fontSize: 12,
                      whiteSpace: "pre-wrap",
                    }}
                  >
{JSON.stringify(resp.reasoning_details ?? {}, null, 2)}
                  </pre>
                )}
              </>
            ) : (
              <div style={{ fontSize: 13, opacity: 0.7 }}>Ask about incidents, alerts, or a component’s health.</div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
