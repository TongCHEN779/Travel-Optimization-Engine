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

export type Flight = {
  id: number; from: string; to: string; dep_min: number; arr_min: number; price: number; airline: string;
  from_city: string; to_city: string; off_from: number; off_to: number; // standard UTC offsets (minutes)
};
export type Itinerary = {
  is_knee: boolean; score: number;
  objectives: Record<ObjKey, number>;
  outbound: Flight[]; inbound: Flight[];
};
export type SearchResponse = {
  pareto_size: number; returned: number; itineraries: Itinerary[];
  stats: { runtime_ms: number; labels_generated: number; labels_kept: number; prune_ratio: number; round_trip_combinations: number };
};
export type Airport = { code: string; name: string; city: string; country: string; region: string; lat: number; lon: number; offset: number; hub: boolean };

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

/** Day 0 of the engine's clock; all day indices are calendar days since this date (a Monday). */
export const EPOCH = "2024-01-01";
const MS_DAY = 86400000;
export const dayOf = (iso: string) => Math.round((Date.parse(iso + "T00:00:00Z") - Date.parse(EPOCH + "T00:00:00Z")) / MS_DAY);
export const isoOf = (day: number) => new Date(Date.parse(EPOCH + "T00:00:00Z") + day * MS_DAY).toISOString().slice(0, 10);
const WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Local wall-clock time at an airport, e.g. "Sat 13 Feb 09:41". `utc` = minutes since epoch UTC. */
export function fmtLocal(utc: number, offset: number): string {
  const l = utc + offset, day = Math.floor(l / 1440), m = l - day * 1440;
  const d = new Date(Date.parse(EPOCH + "T00:00:00Z") + day * MS_DAY);
  return `${WD[((day % 7) + 7) % 7]} ${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** Min-max normalise (0 = best) over the given itineraries. */
export function normalise(items: Itinerary[]): number[][] {
  const lo = OBJ.map((k) => Math.min(...items.map((i) => i.objectives[k])));
  const hi = OBJ.map((k) => Math.max(...items.map((i) => i.objectives[k])));
  return items.map((i) => OBJ.map((k, j) => (hi[j] > lo[j] ? (i.objectives[k] - lo[j]) / (hi[j] - lo[j]) : 0)));
}
