// Airport autocomplete ranking checks. Run: npm run verify
import { readFileSync } from "node:fs";
import type { Airport } from "../lib/api";
import { searchAirports } from "../lib/search";

const w = JSON.parse(readFileSync(new URL("../public/data/world.json", import.meta.url), "utf8"));
const airports: Airport[] = w.airports;
const codes = (q: string) => searchAirports(airports, q).map((a) => a.code);

const cases: [string, (c: string[]) => boolean, string][] = [
  ["sin", (c) => c[0] === "SIN", "IATA code ranks first"],
  ["Tokyo", (c) => c.includes("NRT") && c.includes("HND") && c.length === 2, "city with two airports"],
  ["tok", (c) => c.includes("NRT") && c.includes("HND"), "prefix"],
  ["东京", (c) => c.includes("NRT") && c.includes("HND"), "Chinese city name"],
  ["伦敦", (c) => c[0] === "LHR", "Chinese city name (single airport)"],
  ["日本", (c) => ["NRT", "HND", "KIX"].every((x) => c.includes(x)), "Chinese country name"],
  ["japan", (c) => ["NRT", "HND", "KIX"].every((x) => c.includes(x)), "English country name"],
  ["uk", (c) => c[0] === "LHR", "country alias"],
  ["sao paulo", (c) => c[0] === "GRU", "diacritics-insensitive (São Paulo)"],
  ["zurich", (c) => c[0] === "ZRH", "diacritics-insensitive (Zürich)"],
  ["new york", (c) => c[0] === "JFK", "multi-word"],
  ["heath", (c) => c[0] === "LHR", "airport name"],
  ["zzzz", (c) => c.length === 0, "no match"],
  ["", (c) => c.length > 0 && c.includes("SIN"), "empty query shows popular airports"],
];

let failed = 0;
for (const [q, ok, why] of cases) {
  const c = codes(q);
  if (!ok(c)) { failed++; console.error(`FAIL search "${q}" (${why}): ${c.join(",")}`); }
}
console.log(`${cases.length - failed}/${cases.length} search cases pass`);
if (failed) process.exit(1);
