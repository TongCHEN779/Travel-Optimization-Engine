/**
 * World model, TypeScript side: expands weekly templates into concrete flights for real calendar days.
 * Mirrors backend/src/tripopt/world.py (`instantiate`, `schedule_window`) with integer-only arithmetic so
 * both produce identical flights (verified by `npm run verify`).
 */
import type { Flt } from "./engine";

export type AirportInfo = { code: string; name: string; city: string; country: string; region: string; lat: number; lon: number; offset: number; hub: boolean };
export type World = {
  epoch: string;
  airlines: { name: string; tier: string }[];
  airports: AirportInfo[];
  templates: [string, string, number, number, number, number, number, number][]; // o,d,localDep,dur,basePrice,airline,risk,mask
};

const DAY = 1440;
export const MAX_STOPS_HORIZON = 4;

/** Days (since epoch) of weekly templates that must be instantiated for a query. */
export function scheduleWindow(from: number, to: number, maxStay: number): [number, number] {
  return [from - 1, to + 3 + maxStay + MAX_STOPS_HORIZON];
}

export function instantiate(w: World, dayFrom: number, dayTo: number): Flt[] {
  const off = new Map(w.airports.map((a) => [a.code, a.offset]));
  const out: Flt[] = [];
  for (let day = dayFrom; day <= dayTo; day++) {
    const wd = ((day % 7) + 7) % 7;
    const weekend = wd === 4 || wd === 6 ? 8 : 0;
    w.templates.forEach((t, ti) => {
      if (!((t[7] >> wd) & 1)) return;
      const h = Math.imul(ti * 7919 + day * 104729, 2654435761) >>> 0;
      const pct = 82 + ((h >>> 8) % 41) + weekend;
      const dep = day * DAY + t[2] - off.get(t[0])!;
      out.push({
        id: day * 10000 + ti, o: t[0], d: t[1], dep, arr: dep + t[3],
        price: Math.floor((t[4] * pct) / 100), airline: t[5], risk: t[6], seats: 1 + ((h >>> 16) % 9),
      });
    });
  }
  return out;
}
