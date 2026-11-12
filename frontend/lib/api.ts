import { localAirports, localSearch } from "./local";

// With NEXT_PUBLIC_API_URL set the UI talks to the FastAPI backend; otherwise the engine runs in the browser.
export const API = process.env.NEXT_PUBLIC_API_URL ?? "";

export const OBJ = ["price", "duration_min", "stops", "wait_min", "risk"] as const;
export type ObjKey = (typeof OBJ)[number];
export const LABEL: Record<ObjKey, string> = {
  price: "Price", duration_min: "Duration", stops: "Stops", wait_min: "Layover wait", risk: "Risk",
};
export const WEIGHT_KEY: Record<ObjKey, string> = {
  price: "price", duration_min: "duration", stops: "stops", wait_min: "wait", risk: "risk",
};

export type Flight = { id: number; from: string; to: string; dep_min: number; arr_min: number; price: number; airline: string };
export type Itinerary = {
  is_knee: boolean; score: number;
  objectives: Record<ObjKey, number>;
  outbound: Flight[]; inbound: Flight[];
};
export type SearchResponse = {
  pareto_size: number; returned: number; itineraries: Itinerary[];
  stats: { runtime_ms: number; labels_generated: number; labels_kept: number; prune_ratio: number; round_trip_combinations: number };
};
export type Airport = { code: string; name: string; x: number; y: number; hub: boolean };

export async function getAirports(): Promise<Airport[]> {
  if (!API) return localAirports();
  const r = await fetch(`${API}/api/v1/airports`);
  if (!r.ok) throw new Error(`airports: ${r.status}`);
  return r.json();
}

export async function search(body: Record<string, unknown>): Promise<SearchResponse> {
  if (!API) return localSearch(body);
  const r = await fetch(`${API}/api/v1/search`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, limit: 500 }),
  });
  if (!r.ok) throw new Error(`${r.status}: ${(await r.json().catch(() => ({}))).detail ?? "search failed"}`);
  return r.json();
}

export function fmt(k: ObjKey, v: number): string {
  if (k === "price") return `$${v.toFixed(0)}`;
  if (k === "duration_min" || k === "wait_min") return `${Math.floor(v / 60)}h ${String(Math.round(v % 60)).padStart(2, "0")}m`;
  if (k === "risk") return `${(100 * (1 - Math.exp(-v))).toFixed(1)}%`; // P(at least one failure)
  return String(Math.round(v));
}

export function fmtTime(min: number): string {
  const d = Math.floor(min / 1440), m = min % 1440;
  return `Day ${d} ${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** Min-max normalise (0 = best) over the given itineraries. */
export function normalise(items: Itinerary[]): number[][] {
  const lo = OBJ.map((k) => Math.min(...items.map((i) => i.objectives[k])));
  const hi = OBJ.map((k) => Math.max(...items.map((i) => i.objectives[k])));
  return items.map((i) => OBJ.map((k, j) => (hi[j] > lo[j] ? (i.objectives[k] - lo[j]) / (hi[j] - lo[j]) : 0)));
}
