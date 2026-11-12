import { Graph, optimizeRoundTrip, type Flt } from "./engine";
import type { Airport, Flight, Itinerary, SearchResponse } from "./api";

export const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

type Network = { airlines: string[]; airports: Airport[]; flights: (number | string)[][] };
let cache: Promise<{ net: Network; graph: Graph }> | null = null;

function load() {
  cache ??= fetch(`${BASE}/data/network.json`).then(async (r) => {
    if (!r.ok) throw new Error(`network.json: ${r.status}`);
    const net: Network = await r.json();
    const flights: Flt[] = net.flights.map((x) => ({
      id: x[0] as number, o: x[1] as string, d: x[2] as string, dep: x[3] as number, arr: x[4] as number,
      price: x[5] as number, airline: x[6] as number, risk: x[7] as number, seats: x[8] as number,
    }));
    return { net, graph: new Graph(flights) };
  });
  return cache;
}

export async function localAirports(): Promise<Airport[]> {
  return (await load()).net.airports;
}

export async function localSearch(body: Record<string, unknown>): Promise<SearchResponse> {
  const { net, graph } = await load();
  const b = body as Record<string, number | string>;
  const t0 = performance.now();
  const res = optimizeRoundTrip(graph, {
    origin: b.origin as string, dest: b.destination as string,
    from: b.depart_from_day as number, to: b.depart_to_day as number,
    minStay: b.min_stay_days as number, maxStay: b.max_stay_days as number,
    c: { maxStops: b.max_stops as number, mct: 60, maxLayover: 480, pax: b.passengers as number },
  });
  const ms = performance.now() - t0;
  const fj = (id: number): Flight => {
    const f = graph.byId.get(id)!;
    return { id, from: f.o, to: f.d, dep_min: f.dep, arr_min: f.arr, price: f.price / 100, airline: net.airlines[f.airline] };
  };
  const itineraries: Itinerary[] = res.front.map((p) => ({
    is_knee: false, score: 0,
    objectives: { price: p.vec[0] / 100, duration_min: p.vec[1], stops: p.vec[2], wait_min: p.vec[3], risk: p.vec[4] / 1e6 },
    outbound: p.flights.slice(0, p.split).map(fj), inbound: p.flights.slice(p.split).map(fj),
  }));
  return {
    pareto_size: itineraries.length, returned: itineraries.length, itineraries,
    stats: { runtime_ms: ms, labels_generated: res.stats.generated, labels_kept: res.stats.kept,
      prune_ratio: res.stats.generated ? 1 - res.stats.kept / res.stats.generated : 0, round_trip_combinations: res.combinations },
  };
}
