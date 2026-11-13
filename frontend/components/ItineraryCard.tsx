"use client";
import { Flight, Itinerary, fmt, fmtLocal } from "@/lib/api";

function Leg({ title, flights }: { title: string; flights: Flight[] }) {
  return (
    <div className="leg">
      <h4>{title}</h4>
      {flights.map((f, i) => (
        <div key={f.id}>
          <div className="flight">
            <b>{f.from_city} ({f.from}) → {f.to_city} ({f.to})</b>
            <span>{fmtLocal(f.dep_min, f.off_from)} → {fmtLocal(f.arr_min, f.off_to)}</span>
            <span className="muted">{f.airline} · ${f.price.toFixed(0)}</span>
          </div>
          {flights[i + 1] && <div className="layover">layover in {f.to_city} ({f.to}): {fmt("wait_min", flights[i + 1].dep_min - f.arr_min)}</div>}
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
        <span className="muted">{fmtLocal(it.outbound[0].dep_min, it.outbound[0].off_from).slice(0, -6)} → {fmtLocal(it.inbound[it.inbound.length - 1].arr_min, it.inbound[it.inbound.length - 1].off_to).slice(0, -6)}</span>
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
