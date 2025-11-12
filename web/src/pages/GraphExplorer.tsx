// web/src/pages/Graph.tsx
import React from "react";
import { getJSON } from "../lib/api";

export default function GraphExplorer() {
  const [etype, setEtype] = React.useState("Service");
  const [eid, setEid] = React.useState("order-service");
  const [data, setData] = React.useState<any>(null);

  async function load(e: React.FormEvent) {
    e.preventDefault();
    const res = await getJSON(`/graph/entity/${etype}/${eid}`);
    setData(res);
  }

  return (
    <section>
      <h2>Graph Explorer (basic)</h2>
      <form onSubmit={load} style={{display:"flex", gap:8, marginBottom:12}}>
        <input value={etype} onChange={(e)=>setEtype(e.target.value)} style={{width:160}} />
        <input value={eid} onChange={(e)=>setEid(e.target.value)} style={{flex:1}} />
        <button type="submit">Load</button>
      </form>
      <pre style={{background:"#111", padding:12, borderRadius:8}}>
        {data ? JSON.stringify(data, null, 2) : "// enter an entity type & id"}
      </pre>
    </section>
  );
}
