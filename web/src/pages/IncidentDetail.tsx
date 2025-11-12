import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

export default function IncidentDetail() {
  const { id } = useParams();
  const [incident, setIncident] = useState<any | null>(null);
  const [timeline, setTimeline] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      const [iRes, tRes] = await Promise.all([
        fetch(`http://localhost:8000/incidents/search?incident_id=${id}`),
        fetch(`http://localhost:8000/events/timeline?incident_id=${id}`)
      ]);
      const iData = await iRes.json();
      const tData = await tRes.json();
      setIncident((iData.incidents || [])[0] || null);
      setTimeline(tData.timeline || []);
    }
    load();
  }, [id]);

  return (
    <section>
      <h1>Incident {id}</h1>
      <h2>Details</h2>
      <pre>{JSON.stringify(incident, null, 2)}</pre>
      <h2>Timeline</h2>
      <pre>{JSON.stringify(timeline, null, 2)}</pre>
    </section>
  );
}
