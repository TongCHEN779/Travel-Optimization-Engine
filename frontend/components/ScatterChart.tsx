"use client";
import { Itinerary, LABEL, OBJ, ObjKey, fmt } from "@/lib/api";

type Props = {
  items: Itinerary[]; selected: number | null; onSelect: (i: number) => void;
  x: ObjKey; y: ObjKey; setX: (k: ObjKey) => void; setY: (k: ObjKey) => void;
};
const W = 560, H = 340, M = { l: 62, r: 16, t: 14, b: 44 };

export default function ScatterChart({ items, selected, onSelect, x, y, setX, setY }: Props) {
  const xs = items.map((i) => i.objectives[x]), ys = items.map((i) => i.objectives[y]);
  const pad = (a: number[]) => { const lo = Math.min(...a), hi = Math.max(...a), p = (hi - lo || 1) * 0.06; return [lo - p, hi + p]; };
  const [x0, x1] = pad(xs), [y0, y1] = pad(ys);
  const sx = (v: number) => M.l + ((v - x0) / (x1 - x0)) * (W - M.l - M.r);
  const sy = (v: number) => H - M.b - ((v - y0) / (y1 - y0)) * (H - M.t - M.b);
  const ticks = (a: number, b: number) => [0, 1, 2, 3, 4].map((t) => a + ((b - a) * t) / 4);
  const stopColor = ["var(--c0)", "var(--c1)", "var(--c2)", "var(--c3)"];
  return (
    <div>
      <div className="row">
        <label>X <select value={x} onChange={(e) => setX(e.target.value as ObjKey)}>{OBJ.map((k) => <option key={k} value={k}>{LABEL[k]}</option>)}</select></label>
        <label>Y <select value={y} onChange={(e) => setY(e.target.value as ObjKey)}>{OBJ.map((k) => <option key={k} value={k}>{LABEL[k]}</option>)}</select></label>
        <span className="muted">colour = total stops · outlined = best compromise</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${LABEL[y]} vs ${LABEL[x]} scatter of Pareto itineraries`}>
        {ticks(x0, x1).map((t, i) => (<g key={`x${i}`}><line x1={sx(t)} x2={sx(t)} y1={M.t} y2={H - M.b} className="grid" /><text x={sx(t)} y={H - M.b + 16} className="tick" textAnchor="middle">{fmt(x, t)}</text></g>))}
        {ticks(y0, y1).map((t, i) => (<g key={`y${i}`}><line x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} className="grid" /><text x={M.l - 8} y={sy(t) + 4} className="tick" textAnchor="end">{fmt(y, t)}</text></g>))}
        <text x={(W + M.l) / 2} y={H - 6} className="axis" textAnchor="middle">{LABEL[x]}</text>
        <text transform={`translate(14 ${(H - M.b) / 2}) rotate(-90)`} className="axis" textAnchor="middle">{LABEL[y]}</text>
        {items.map((it, i) => (
          <circle key={i} cx={sx(it.objectives[x])} cy={sy(it.objectives[y])} r={selected === i ? 8 : it.is_knee ? 7 : 5}
            fill={stopColor[Math.min(3, it.objectives.stops)]} className={selected === i ? "pt sel" : "pt"}
            stroke={it.is_knee || selected === i ? "var(--fg)" : "none"} strokeWidth={2} onClick={() => onSelect(i)}>
            <title>{`${fmt("price", it.objectives.price)} · ${fmt("duration_min", it.objectives.duration_min)} · ${it.objectives.stops} stops`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
