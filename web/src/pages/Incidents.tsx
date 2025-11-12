// web/src/pages/Incidents.tsx
import React, { useEffect, useState } from "react";
import ProposedActions from "../components/ProposedActions";
import AgentActionsAudit from "../components/AgentActionsAudit";

const API = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8000";

type Incident = {
  incident_id: string;
  summary: string;
  severity: string;
  status: string;
};

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setErr("");
        const [inc, al] = await Promise.all([
          fetch(`${API}/incidents/search?status=investigating`).then(r=>r.json()),
          fetch(`${API}/events/alerts/active`).then(r=>r.json())
        ]);
        setIncidents(inc?.incidents || []);
        setAlerts(al?.alerts || []);
      } catch (e:any) {
        setErr(e.message || "Failed to load incidents/alerts");
      }
    })();
  }, []);

  return (
    <section>
      <h1>Active Incidents</h1>
      {err && <div style={{color:"tomato"}}>Error: {err}</div>}
      <table style={{width:"100%", borderCollapse:"collapse"}}>
        <thead>
          <tr>
            <th style={{textAlign:"left"}}>Incident</th>
            <th style={{textAlign:"left"}}>Severity</th>
            <th style={{textAlign:"left"}}>Status</th>
            <th style={{textAlign:"left"}}>Summary</th>
          </tr>
        </thead>
        <tbody>
          {incidents.length === 0 ? (
            <tr><td colSpan={4} style={{opacity:0.7}}>No active incidents.</td></tr>
          ) : incidents.map(i => (
            <tr key={i.incident_id} style={{borderTop:"1px solid #444"}}>
              <td>{i.incident_id}</td>
              <td>{i.severity}</td>
              <td>{i.status}</td>
              <td>{i.summary}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 style={{marginTop:24}}>Active Alerts</h2>
      <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(alerts, null, 2)}</pre>

      {/* Proposed actions + Audit here too so NOC can act */}
      <ProposedActions />
      <AgentActionsAudit />
    </section>
  );
}
