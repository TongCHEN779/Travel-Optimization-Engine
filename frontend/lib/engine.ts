/**
 * In-browser port of the Python engine (backend/src/tripopt): temporal flight DAG,
 * exact multi-objective label-setting with dominance pruning, and the stay-coupled
 * round-trip combination. All objective values are integers (cents, minutes, micro-risk),
 * so results are bit-for-bit comparable with the Python engine (see `npm run verify`).
 */

const DAY = 1440;
type Vec = number[]; // [price, duration, stops, wait, risk]

export type Flt = { id: number; o: string; d: string; dep: number; arr: number; price: number; airline: number; risk: number; seats: number };
export type Constraints = {
  maxStops: number; mct: number; maxLayover: number; pax: number;
  maxPrice?: number | null; maxDuration?: number | null; maxWait?: number | null; maxRisk?: number | null;
};
/** from/to/stay are local calendar days (days since the epoch); offO/offD are standard UTC offsets in minutes. */
export type RoundTripQuery = { origin: string; dest: string; from: number; to: number; minStay: number; maxStay: number; c: Constraints; offO?: number; offD?: number };
export type Path = { flights: number[]; vec: Vec; split?: number };
export type Stats = { generated: number; kept: number };

const lowerBound = (a: number[], x: number) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] < x) lo = m + 1; else hi = m; } return lo; };
const upperBound = (a: number[], x: number) => { let lo = 0, hi = a.length; while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= x) lo = m + 1; else hi = m; } return lo; };

export function connectionRisk(layover: number, mct: number): number {
  const p = 0.3 * Math.exp(-(layover - mct) / 45);
  return Math.round(-Math.log(1 - p) * 1e6);
}

/** Keep one item per distinct non-dominated vector (lexicographic sort + forward pass). */
export function paretoFilter<T>(items: T[], key: (t: T) => Vec): T[] {
  if (items.length <= 1) return items.slice();
  const rows = items.map((it) => ({ it, v: key(it) }));
  rows.sort((a, b) => { for (let i = 0; i < a.v.length; i++) if (a.v[i] !== b.v[i]) return a.v[i] - b.v[i]; return 0; });
  const kept: { it: T; v: Vec }[] = [];
  outer: for (const r of rows) {
    for (const k of kept) {
      let le = true;
      for (let i = 0; i < r.v.length; i++) if (k.v[i] > r.v[i]) { le = false; break; }
      if (le) continue outer; // dominated by (or equal to) a kept vector
    }
    kept.push(r);
  }
  return kept.map((k) => k.it);
}

export class Graph {
  byId = new Map<number, Flt>();
  byOrigin = new Map<string, Flt[]>();
  depKeys = new Map<string, number[]>();
  arrivals = new Map<string, Flt[]>();
  arrKeys = new Map<string, number[]>();

  constructor(public flights: Flt[]) {
    for (const f of flights) {
      this.byId.set(f.id, f);
      (this.byOrigin.get(f.o) ?? this.byOrigin.set(f.o, []).get(f.o)!).push(f);
      (this.arrivals.get(f.d) ?? this.arrivals.set(f.d, []).get(f.d)!).push(f);
    }
    for (const [k, l] of this.byOrigin) { l.sort((a, b) => a.dep - b.dep); this.depKeys.set(k, l.map((f) => f.dep)); }
    for (const [k, l] of this.arrivals) { l.sort((a, b) => a.arr - b.arr); this.arrKeys.set(k, l.map((f) => f.arr)); }
  }

  /** Flights reachable within maxStops connections, sorted by departure (layered forward BFS). */
  usable(origin: string, dest: string, depFrom: number, depTo: number, c: Constraints): Flt[] {
    const ok = (f: Flt) => f.d !== origin && f.o !== dest && f.seats >= c.pax;
    const keys = this.depKeys.get(origin) ?? [];
    const lst = this.byOrigin.get(origin) ?? [];
    let layer = lst.slice(lowerBound(keys, depFrom), upperBound(keys, depTo)).filter(ok);
    const seen = new Map<number, Flt>(layer.map((f) => [f.id, f]));
    for (let s = 0; s < c.maxStops && layer.length; s++) {
      const next: Flt[] = [];
      for (const f of layer) {
        if (f.d === dest) continue;
        const ks = this.depKeys.get(f.d);
        if (!ks) continue;
        const a = lowerBound(ks, f.arr + c.mct), b = upperBound(ks, f.arr + c.maxLayover);
        const out = this.byOrigin.get(f.d)!;
        for (let i = a; i < b; i++) { const g = out[i]; if (!seen.has(g.id) && ok(g)) { seen.set(g.id, g); next.push(g); } }
      }
      layer = next;
    }
    return [...seen.values()].sort((a, b) => a.dep - b.dep);
  }

  predecessors(g: Flt, c: Constraints, allowed: Set<number>): Flt[] {
    const ks = this.arrKeys.get(g.o);
    if (!ks) return [];
    const lo = lowerBound(ks, g.dep - c.maxLayover), hi = upperBound(ks, g.dep - c.mct);
    return this.arrivals.get(g.o)!.slice(lo, hi).filter((f) => allowed.has(f.id));
  }
}

type Label = { v: Vec; parent: [number, number] | null };

function legFronts(g: Graph, origin: string, dest: string, depFrom: number, depTo: number, c: Constraints, byArrDay: boolean, stats: Stats, arrOffset = 0): Map<number, Path[]> {
  const bounds: [number, number | null | undefined][] = [[0, c.maxPrice], [1, c.maxDuration], [3, c.maxWait], [4, c.maxRisk]];
  const finite = bounds.filter(([, b]) => b != null) as [number, number][];
  const flights = g.usable(origin, dest, depFrom, depTo, c);
  const allowed = new Set(flights.map((f) => f.id));
  const labels = new Map<number, Label[]>();
  const withinBounds = (v: Vec) => finite.every(([i, b]) => v[i] <= b);

  for (const f of flights) {
    const isStart = f.o === origin;
    if (isStart && !(f.dep >= depFrom && f.dep <= depTo)) continue;
    const pg = f.price * c.pax, dg = f.arr - f.dep;
    let cands: Label[] = [];
    if (isStart) {
      const v = [pg, dg, 0, 0, f.risk];
      stats.generated++;
      if (withinBounds(v)) cands.push({ v, parent: null });
    } else {
      for (const p of g.predecessors(f, c, allowed)) {
        const pl = labels.get(p.id);
        if (!pl) continue;
        const lay = f.dep - p.arr, risk = f.risk + connectionRisk(lay, c.mct);
        pl.forEach((l, idx) => {
          if (l.v[2] >= c.maxStops) return;
          const v = [l.v[0] + pg, l.v[1] + dg + lay, l.v[2] + 1, l.v[3] + lay, l.v[4] + risk];
          stats.generated++;
          if (withinBounds(v)) cands.push({ v, parent: [p.id, idx] });
        });
      }
    }
    if (cands.length) { cands = paretoFilter(cands, (l) => l.v); labels.set(f.id, cands); stats.kept += cands.length; }
  }

  const rebuild = (fid: number, idx: number): number[] => {
    const path: number[] = [];
    let cur: [number, number] | null = [fid, idx];
    while (cur) { path.push(cur[0]); cur = labels.get(cur[0])![cur[1]].parent; }
    return path.reverse();
  };
  const groups = new Map<number, Path[]>();
  for (const [fid, ls] of labels) {
    const f = g.byId.get(fid)!;
    if (f.d !== dest) continue;
    const key = byArrDay ? Math.floor((f.arr + arrOffset) / DAY) : 0;
    const arr = groups.get(key) ?? groups.set(key, []).get(key)!;
    ls.forEach((l, idx) => arr.push({ flights: rebuild(fid, idx), vec: l.v }));
  }
  for (const [k, v] of groups) groups.set(k, paretoFilter(v, (p) => p.vec));
  return groups;
}

export function optimizeRoundTrip(g: Graph, q: RoundTripQuery): { front: Path[]; stats: Stats; combinations: number } {
  const stats: Stats = { generated: 0, kept: 0 };
  const c = q.c;
  const oo = q.offO ?? 0, od = q.offD ?? 0;
  const outByDay = legFronts(g, q.origin, q.dest, q.from * DAY - oo, (q.to + 1) * DAY - 1 - oo, c, true, stats, od);
  if (!outByDay.size) return { front: [], stats, combinations: 0 };

  const retDays = new Set<number>();
  for (const a of outByDay.keys()) for (let s = q.minStay; s <= q.maxStay; s++) retDays.add(a + s);
  const totals: (number | null | undefined)[] = [c.maxPrice, c.maxDuration, null, c.maxWait, c.maxRisk];
  const results: Path[] = [];
  let combinations = 0;
  for (const r of [...retDays].sort((a, b) => a - b)) {
    const back = legFronts(g, q.dest, q.origin, r * DAY - od, (r + 1) * DAY - 1 - od, c, false, stats).get(0);
    if (!back?.length) continue;
    let pool: Path[] = [];
    for (const [a, lst] of outByDay) if (r - a >= q.minStay && r - a <= q.maxStay) pool = pool.concat(lst);
    if (!pool.length) continue;
    pool = paretoFilter(pool, (p) => p.vec);
    const cand: Path[] = [];
    for (const A of pool) for (const B of back) {
      combinations++;
      const v = A.vec.map((x, i) => x + B.vec[i]);
      if (totals.every((lim, i) => lim == null || v[i] <= lim)) cand.push({ flights: A.flights.concat(B.flights), vec: v, split: A.flights.length });
    }
    results.push(...paretoFilter(cand, (p) => p.vec));
  }
  return { front: paretoFilter(results, (p) => p.vec), stats, combinations };
}
