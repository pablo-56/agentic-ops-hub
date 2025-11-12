import React from "react";
import { Routes, Route, Link } from "react-router-dom";
import  Home  from "./pages/Home";
import Incidents  from "./pages/Incidents";
import  IncidentDetail  from "./pages/IncidentDetail";
import  GraphExplorer  from "./pages/GraphExplorer";
import  PlantOverview  from "./pages/PlantOverview";
import  ServiceDetail  from "./pages/ServiceDetail";
import  Runbooks  from "./pages/Runbooks";
import  Reports  from "./pages/Reports";
import  AgentDock  from "./components/AgentDock";
import  NotificationCenter  from "./components/NotificationCenter";

export default function App() {
  return (
    <div>
      <header style={{display:'flex',justifyContent:'space-between',padding:'8px',borderBottom:'1px solid #eee'}}>
        <nav style={{display:'flex',gap:'12px'}}>
          <Link to="/">Command Center</Link>
          <Link to="/incidents">Incidents</Link>
          <Link to="/graph">Graph</Link>
          <Link to="/runbooks">Runbooks</Link>
          <Link to="/reports">Reports</Link>
        </nav>
        <NotificationCenter />
      </header>
      <main style={{paddingRight:'320px',padding:'16px'}}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          <Route path="/graph" element={<GraphExplorer />} />
          <Route path="/plant/:id" element={<PlantOverview />} />
          <Route path="/service/:name" element={<ServiceDetail />} />
          <Route path="/runbooks" element={<Runbooks />} />
          <Route path="/reports" element={<Reports />} />
        </Routes>
      </main>
      <AgentDock />
    </div>
  );
}
