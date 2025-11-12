// web/src/components/StreamTicker.tsx
import React, { useEffect, useRef, useState } from "react";
import { openStreamSocket } from "../api/index";

/**
 * Live Event/Incident Ticker
 * - Connects to WS /ws/stream
 * - Renders latest ~50 events as JSON blobs
 */
export function StreamTicker() {
  const [events, setEvents] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = openStreamSocket();
    wsRef.current = ws;

    // Optionally send a filter message to your stub
    ws.addEventListener("open", () => ws.send(JSON.stringify({ subscribe: "incidents_and_alerts" })));

    ws.addEventListener("message", (e) => {
      try {
        const data = JSON.parse(e.data as string);
        setEvents((prev) => [data, ...prev].slice(0, 50));
      } catch {
        // Your stub echoes text; capture that too
        setEvents((prev) => [{ raw: e.data }, ...prev].slice(0, 50));
      }
    });

    return () => ws.close();
  }, []);

  return (
    <div className="border rounded p-4 bg-white">
      <h2 className="text-lg font-semibold mb-2">Live Event Stream</h2>
      <div className="h-96 overflow-y-auto border p-2 rounded bg-gray-50">
        {events.map((evt, i) => (
          <pre key={i} className="p-2 mb-2 bg-gray-200 rounded text-xs whitespace-pre-wrap">
            {JSON.stringify(evt, null, 2)}
          </pre>
        ))}
        {events.length === 0 && <div className="text-sm text-gray-500">No events yet.</div>}
      </div>
    </div>
  );
}
