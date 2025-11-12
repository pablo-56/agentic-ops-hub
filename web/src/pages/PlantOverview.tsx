import React from "react";
import { useParams } from "react-router-dom";

export default function PlantOverview() {
  const { id } = useParams();
  return (
    <section>
      <h1>Plant {id} Overview</h1>
      <p>KPIs, anomalies, and agent insights will display here.</p>
    </section>
  );
}
