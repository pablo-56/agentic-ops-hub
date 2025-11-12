import React, { useEffect, useState } from "react";

export default function NotificationCenter() {
  const [items, setItems] = useState<string[]>([]);

  useEffect(()=>{
    const ws = new WebSocket("ws://localhost:8000/ws/stream");
    ws.onopen = ()=> ws.send(JSON.stringify({subscribe:"incidents-and-alerts"}));
    ws.onmessage = (ev)=> setItems(prev => [ev.data, ...prev].slice(0,5));
    return ()=> ws.close();
  },[]);

  return (
    <div>
      <strong>Notifications</strong>
      <div style={{fontSize:12,opacity:0.8}}>{items.length ? `${items.length} recent` : "none"}</div>
    </div>
  );
}
