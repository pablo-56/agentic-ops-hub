// web/src/components/StatCard.tsx
import React from "react";

export function StatCard(props: { title: string; value: React.ReactNode; subtitle?: string }) {
  return (
    <div className="p-4 border rounded shadow bg-white">
      <div className="text-sm text-gray-600">{props.title}</div>
      <div className="text-3xl font-semibold">{props.value}</div>
      {props.subtitle && <div className="text-xs text-gray-500 mt-1">{props.subtitle}</div>}
    </div>
  );
}
