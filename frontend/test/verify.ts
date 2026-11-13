// Checks that the TypeScript engine + schedule generator reproduce the Python engine's Pareto fronts exactly.
// Run: npm run verify   (fixtures: backend/scripts/export_network.py)
import { readFileSync } from "node:fs";
import { Graph, optimizeRoundTrip } from "../lib/engine";
import { instantiate, scheduleWindow, type World } from "../lib/world";

const world: World = JSON.parse(readFileSync(new URL("../public/data/world.json", import.meta.url), "utf8"));
const golden = JSON.parse(readFileSync(new URL("./golden.json", import.meta.url), "utf8"));
const off = new Map(world.airports.map((a) => [a.code, a.offset]));

let failed = 0, nonEmpty = 0, points = 0;
for (const [i, t] of golden.entries()) {
  const q = t.query;
  const [lo, hi] = scheduleWindow(q.from, q.to, q.maxStay);
  const g = new Graph(instantiate(world, lo, hi));
  const res = optimizeRoundTrip(g, {
    origin: q.origin, dest: q.dest, from: q.from, to: q.to, minStay: q.minStay, maxStay: q.maxStay,
    offO: off.get(q.origin), offD: off.get(q.dest),
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
