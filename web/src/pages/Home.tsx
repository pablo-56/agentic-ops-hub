// web/src/pages/Home.tsx
import React from "react";
import { getJSON, postJSON } from "../lib/api";


export default function Home() {
  const [summary, setSummary] = React.useState<any>(null);
  const [alerts, setAlerts] = React.useState<any>(null);
  const [query, setQuery] = React.useState("");
  const [agent, setAgent] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(false);

  // Load health summary + active alerts
  React.useEffect(() => {
    Promise.all([
      getJSON("/graph/topology-summary"),
      getJSON("/events/alerts/active"),
    ]).then(([s, a]) => { setSummary(s); setAlerts(a); }).catch(console.error);
  }, []);

  async function askAgent(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await postJSON("/agent/query", { message: query, scope: null });
      setAgent(res);
    } catch (err) {
      setAgent({ reply: String(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={{display:"grid", gridTemplateColumns:"1fr 1fr", gap:16}}>
      <div>
        <h2>Global Health</h2>
        <pre style={{background:"#111", padding:12, borderRadius:8}}>
          {JSON.stringify(summary, null, 2)}
        </pre>

        <h3>Active Alerts</h3>
        <pre style={{background:"#111", padding:12, borderRadius:8}}>
          {JSON.stringify(alerts, null, 2)}
        </pre>
      </div>
    </section>
  );
}
