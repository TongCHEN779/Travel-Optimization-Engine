// Checks that the TypeScript engine reproduces the Python engine's Pareto fronts exactly.
// Run: npm run verify   (fixtures: backend/scripts/export_network.py)
import { readFileSync } from "node:fs";
import { Graph, optimizeRoundTrip, type Flt } from "../lib/engine";

const net = JSON.parse(readFileSync(new URL("../public/data/network.json", import.meta.url), "utf8"));
const golden = JSON.parse(readFileSync(new URL("./golden.json", import.meta.url), "utf8"));
const flights: Flt[] = net.flights.map((r: number[] & string[]) => ({
  id: r[0], o: r[1], d: r[2], dep: r[3], arr: r[4], price: r[5], airline: r[6], risk: r[7], seats: r[8],
}));
const g = new Graph(flights);

let failed = 0, nonEmpty = 0, points = 0;
for (const [i, t] of golden.entries()) {
  const q = t.query;
  const res = optimizeRoundTrip(g, {
    origin: q.origin, dest: q.dest, from: q.from, to: q.to, minStay: q.minStay, maxStay: q.maxStay,
    c: { maxStops: q.maxStops, mct: q.mct, maxLayover: q.maxLayover, pax: q.pax, maxPrice: q.maxPrice, maxDuration: q.maxDuration },
  });
  const got = res.front.map((p) => p.vec.join(",")).sort();
  const want = (t.front as number[][]).map((v) => v.join(",")).sort();
  const ok = got.length === want.length && got.every((x, k) => x === want[k]);
  if (!ok) { failed++; console.error(`case ${i} ${q.origin}->${q.dest}: MISMATCH got ${got.length} want ${want.length}`); }
  if (want.length) { nonEmpty++; points += want.length; }
}
console.log(`${golden.length - failed}/${golden.length} cases match Python (${nonEmpty} non-empty, ${points} Pareto points compared)`);
if (failed || !nonEmpty) process.exit(1);
