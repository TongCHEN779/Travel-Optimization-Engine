"use client";
import { Itinerary, LABEL, OBJ, fmt, normalise } from "@/lib/api";

const W = 560, H = 260, M = { l: 40, r: 40, t: 28, b: 14 };

export default function ParallelCoords({ items, selected, onSelect }: { items: Itinerary[]; selected: number | null; onSelect: (i: number) => void }) {
  if (!items.length) return null;
  const N = normalise(items);
  const ax = (j: number) => M.l + (j * (W - M.l - M.r)) / (OBJ.length - 1);
  const ay = (v: number) => M.t + v * (H - M.t - M.b);
  const path = (row: number[]) => row.map((v, j) => `${j ? "L" : "M"}${ax(j)},${ay(v)}`).join("");
  const order = items.map((_, i) => i).sort((a, b) => (a === selected ? 1 : b === selected ? -1 : 0));
  const lo = OBJ.map((k) => Math.min(...items.map((i) => i.objectives[k])));
  const hi = OBJ.map((k) => Math.max(...items.map((i) => i.objectives[k])));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Parallel coordinates of all objectives; top is best">
      {OBJ.map((k, j) => (
        <g key={k}>
          <line x1={ax(j)} x2={ax(j)} y1={M.t} y2={H - M.b} className="axisline" />
          <text x={ax(j)} y={12} className="axis" textAnchor="middle">{LABEL[k]}</text>
          <text x={ax(j)} y={M.t - 4} className="tick" textAnchor="middle">{fmt(k, lo[j])}</text>
          <text x={ax(j)} y={H - 1} className="tick" textAnchor="middle">{fmt(k, hi[j])}</text>
        </g>
      ))}
      {order.map((i) => (
        <path key={i} d={path(N[i])} fill="none" className={i === selected ? "line sel" : "line"}
          stroke={i === selected ? "var(--accent)" : items[i].is_knee ? "var(--fg)" : "var(--line)"}
          strokeWidth={i === selected ? 3 : items[i].is_knee ? 2 : 1.2} onClick={() => onSelect(i)} />
      ))}
    </svg>
  );
}
