// web/src/api/index.ts
// Small typed client for your FastAPI backend.
// Uses VITE_API_BASE (fallback to http://localhost:8000)

export const API_BASE =
  import.meta.env.VITE_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

type Json = Record<string, any>;

async function get<T = any>(path: string, params?: Record<string, any>): Promise<T> {
  const qs = params ? `?${new URLSearchParams(params as any).toString()}` : "";
  const res = await fetch(`${API_BASE}${path}${qs}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T = any>(path: string, body?: Json): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

// --- Endpoints used by Home --------------------------------------------------

// Topology summary cards (plants/services/incidents)
export function getTopologySummary() {
  return get<{ scope: any; summary: { plants: number; services: number; incidents: number } }>(
    "/graph/topology-summary"
  );
}

// Active alerts list (stubbed for now)
export function getActiveAlerts(params?: { entity_type?: string; entity_id?: string; severity?: string }) {
  return get<{ alerts: any[] }>("/events/alerts/active", params);
}

// Search incidents (e.g., status=investigating)
export function searchIncidents(params?: { status?: string; entity_type?: string; entity_id?: string; window?: string }) {
  return get<{ incidents: any[] }>("/incidents/search", params);
}

// Create incident (quick form)
export function createIncident(payload: { summary: string; severity: string; entities?: Array<Record<string, any>> }) {
  return post<{ incident_id: string; status: string }>("/incidents/", payload);
}

// Ask Ops Copilot (your AgentQuery expects { message, scope? })
export function askAgent(message: string, scope?: Record<string, any>) {
  return post<{ reply: string; confidence: number; reasoning_summary: string }>(
    "/agent/query",
    { message, scope }
  );
}

// WebSocket opener for the live stream
export function openStreamSocket(): WebSocket {
  // Use API_BASE host to avoid hardcoding localhost/ports
  const u = new URL(API_BASE);
  const wsUrl = `${u.protocol === "https:" ? "wss" : "ws"}://${u.host}/ws/stream`;
  return new WebSocket(wsUrl);
}
