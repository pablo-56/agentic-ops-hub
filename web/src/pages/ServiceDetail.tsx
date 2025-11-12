import React from "react";
import { useParams } from "react-router-dom";

export default function ServiceDetail() {
  const { name } = useParams();
  return (
    <section>
      <h1>Service {name}</h1>
      <p>Dependencies, incidents, and deployment history will display here.</p>
    </section>
  );
}
