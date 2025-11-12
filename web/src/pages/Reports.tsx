// web/src/pages/Reports.tsx
import React from "react";
import { getJSON } from "../lib/api";

export default function Reports() {
  const [data, setData] = React.useState<any>(null);

  React.useEffect(() => {
    // Simple “shift handover” style: last 24h incidents + timeline stub
    Promise.all([
      getJSON("/incidents/search?window=24h"),
      getJSON("/events/timeline?window=2h"),
    ]).then(([incs, tl]) => setData({incs, tl})).catch(console.error);
  }, []);

  return (
    <section>
      <h2>Reports (Last 24h)</h2>
      <pre style={{background:"#111", padding:12, borderRadius:8}}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </section>
  );
}
