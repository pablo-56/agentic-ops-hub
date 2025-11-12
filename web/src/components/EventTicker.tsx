// web/src/components/EventTicker.tsx
import React from "react";

export function EventTicker() {
  const [messages, setMessages] = React.useState<string[]>([]);

  React.useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/stream");
    ws.onopen = () => ws.send("subscribe: all");
    ws.onmessage = (evt) => {
      try {
        // pretty print JSON event; fall back to text
        const asObj = JSON.parse(evt.data);
        setMessages((m) => [`${asObj.topic} @ ${asObj.ts}`, ...m].slice(0, 12));
      } catch {
        setMessages((m) => [evt.data, ...m].slice(0, 12));
      }
    };
    return () => ws.close();
  }, []);

  return (
    <div style={{border:"1px solid #333", padding: 8, borderRadius: 8}}>
      <strong>Live Ticker</strong>
      <ul style={{margin: 0, paddingLeft: 16}}>
        {messages.map((m, i) => <li key={i} style={{fontFamily:"monospace"}}>{m}</li>)}
      </ul>
    </div>
  );
}
