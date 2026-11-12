"use client";
import { Flight, Itinerary, fmt, fmtTime } from "@/lib/api";

function Leg({ title, flights }: { title: string; flights: Flight[] }) {
  return (
    <div className="leg">
      <h4>{title}</h4>
      {flights.map((f, i) => (
        <div key={f.id}>
          <div className="flight">
            <b>{f.from} → {f.to}</b>
            <span>{fmtTime(f.dep_min)} – {fmtTime(f.arr_min)}</span>
            <span className="muted">{f.airline} · ${f.price.toFixed(0)}</span>
          </div>
          {flights[i + 1] && <div className="layover">layover at {f.to}: {fmt("wait_min", flights[i + 1].dep_min - f.arr_min)}</div>}
        </div>
      ))}
    </div>
  );
}

export default function ItineraryCard({ it, rank, active, onClick }: { it: Itinerary; rank: number; active: boolean; onClick: () => void }) {
  const o = it.objectives;
  return (
    <div className={`card ${active ? "active" : ""}`} onClick={onClick} role="button" tabIndex={0}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onClick()}>
      <div className="head">
        <span className="rank">#{rank}</span>
        <b>{fmt("price", o.price)}</b>
        <span>{fmt("duration_min", o.duration_min)} in transit</span>
        <span>{o.stops} {o.stops === 1 ? "stop" : "stops"}</span>
        <span>risk {fmt("risk", o.risk)}</span>
        {it.is_knee && <span className="badge">best compromise</span>}
      </div>
      {active && (<><Leg title="Outbound" flights={it.outbound} /><Leg title="Return" flights={it.inbound} /></>)}
    </div>
  );
}
