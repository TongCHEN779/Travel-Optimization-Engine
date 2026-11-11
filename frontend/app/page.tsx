"use client";
import { useEffect, useMemo, useState } from "react";
import ItineraryCard from "@/components/ItineraryCard";
import ParallelCoords from "@/components/ParallelCoords";
import ScatterChart from "@/components/ScatterChart";
import { Airport, Itinerary, LABEL, OBJ, ObjKey, SearchResponse, WEIGHT_KEY, fmt, getAirports, normalise, search } from "@/lib/api";

const CAP_KEYS: ObjKey[] = ["price", "duration_min", "wait_min", "risk"];

export default function Home() {
  const [airports, setAirports] = useState<Airport[]>([]);
  const [form, setForm] = useState({ origin: "", destination: "", from: 2, to: 4, minStay: 3, maxStay: 7, pax: 1, stops: 2 });
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [weights, setWeights] = useState<Record<ObjKey, number>>({ price: 3, duration_min: 2, stops: 1, wait_min: 1, risk: 1 });
  const [caps, setCaps] = useState<Partial<Record<ObjKey, number>>>({});
  const [sel, setSel] = useState<number | null>(null); // index into res.itineraries
  const [sx, setSx] = useState<ObjKey>("duration_min");
  const [sy, setSy] = useState<ObjKey>("price");

  useEffect(() => {
    getAirports().then((a) => {
      setAirports(a);
      setForm((f) => ({ ...f, origin: a[5]?.code ?? a[0].code, destination: a[20]?.code ?? a[1].code }));
    }).catch((e) => setErr(`Cannot reach API (${e.message}). Start it: uvicorn tripopt.api.main:app`));
  }, []);

  async function run() {
    setBusy(true); setErr(null);
    try {
      const r = await search({
        origin: form.origin, destination: form.destination, depart_from_day: form.from, depart_to_day: form.to,
        min_stay_days: form.minStay, max_stay_days: form.maxStay, passengers: form.pax, max_stops: form.stops,
      });
      setRes(r); setCaps({}); setSel(null);
    } catch (e) { setErr((e as Error).message); setRes(null); }
    finally { setBusy(false); }
  }

  const ranges = useMemo(() => {
    const r: Partial<Record<ObjKey, [number, number]>> = {};
    if (res?.itineraries.length) for (const k of CAP_KEYS) {
      const v = res.itineraries.map((i) => i.objectives[k]);
      r[k] = [Math.min(...v), Math.max(...v)];
    }
    return r;
  }, [res]);

  // Hard constraints and weights are applied client-side: filtering the exact Pareto front by upper bounds
  // yields exactly the constrained front (see docs/MODEL.md, lemma), so no re-query is needed.
  const visible = useMemo(() => {
    if (!res) return [] as { it: Itinerary; idx: number }[];
    const rows = res.itineraries.map((it, idx) => ({ it, idx }))
      .filter(({ it }) => CAP_KEYS.every((k) => caps[k] === undefined || it.objectives[k] <= caps[k]!));
    if (!rows.length) return rows;
    const N = normalise(rows.map((r) => r.it));
    const wsum = OBJ.reduce((s, k) => s + weights[k], 0) || 1;
    const knee = N.reduce((b, row, i) => (Math.hypot(...row) < Math.hypot(...N[b]) ? i : b), 0);
    return rows
      .map((r, i) => ({ it: { ...r.it, is_knee: i === knee }, idx: r.idx, s: N[i].reduce((a, v, j) => a + v * weights[OBJ[j]], 0) / wsum }))
      .sort((a, b) => a.s - b.s);
  }, [res, caps, weights]);

  const items = visible.map((v) => v.it);
  const selPos = visible.findIndex((v) => v.idx === sel);

  return (
    <main>
      <header>
        <h1>Travel Optimization Engine</h1>
        <p className="muted">Exact Pareto-optimal round trips over price, duration, stops, layover wait and risk. Synthetic network.</p>
      </header>
      <div className="layout">
        <aside>
          <section>
            <h2>Trip</h2>
            <label>From<select value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })}>{airports.map((a) => <option key={a.code} value={a.code}>{a.code}{a.hub ? " (hub)" : ""}</option>)}</select></label>
            <label>To<select value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })}>{airports.map((a) => <option key={a.code} value={a.code}>{a.code}{a.hub ? " (hub)" : ""}</option>)}</select></label>
            <div className="two">
              <label>Depart from day<input type="number" min={0} max={19} value={form.from} onChange={(e) => setForm({ ...form, from: +e.target.value })} /></label>
              <label>to day<input type="number" min={0} max={19} value={form.to} onChange={(e) => setForm({ ...form, to: +e.target.value })} /></label>
              <label>Min stay (days)<input type="number" min={1} value={form.minStay} onChange={(e) => setForm({ ...form, minStay: +e.target.value })} /></label>
              <label>Max stay (days)<input type="number" min={1} value={form.maxStay} onChange={(e) => setForm({ ...form, maxStay: +e.target.value })} /></label>
              <label>Travellers<input type="number" min={1} max={9} value={form.pax} onChange={(e) => setForm({ ...form, pax: +e.target.value })} /></label>
              <label>Max stops / leg<select value={form.stops} onChange={(e) => setForm({ ...form, stops: +e.target.value })}>{[0, 1, 2, 3].map((n) => <option key={n}>{n}</option>)}</select></label>
            </div>
            <button onClick={run} disabled={busy || !form.origin}>{busy ? "Optimising…" : "Find Pareto itineraries"}</button>
          </section>

          {res && res.pareto_size > 0 && (<>
            <section>
              <h2>Preferences <span className="muted">(live re-rank)</span></h2>
              {OBJ.map((k) => (
                <label key={k} className="slider">{LABEL[k]} <span className="muted">{weights[k]}</span>
                  <input type="range" min={0} max={10} value={weights[k]} onChange={(e) => setWeights({ ...weights, [k]: +e.target.value })} aria-label={`${WEIGHT_KEY[k]} weight`} />
                </label>
              ))}
            </section>
            <section>
              <h2>Hard limits</h2>
              {CAP_KEYS.map((k) => {
                const r = ranges[k]; if (!r || r[0] === r[1]) return null;
                const v = caps[k] ?? r[1];
                return (
                  <label key={k} className="slider">{LABEL[k]} ≤ <b>{fmt(k, v)}</b>
                    <input type="range" min={r[0]} max={r[1]} step={k === "risk" ? 0.01 : 1} value={v}
                      onChange={(e) => setCaps({ ...caps, [k]: +e.target.value })} aria-label={`max ${LABEL[k]}`} />
                  </label>
                );
              })}
              <button className="ghost" onClick={() => setCaps({})}>Reset limits</button>
            </section>
          </>)}
        </aside>

        <section className="results">
          {err && <div className="error" role="alert">{err}</div>}
          {!res && !err && <p className="muted empty">Pick a route and run a search.</p>}
          {res && res.pareto_size === 0 && <p className="muted empty">No feasible itinerary. Widen dates, stay range or stops.</p>}
          {res && res.pareto_size > 0 && (<>
            <div className="stats">
              <div><b>{res.pareto_size}</b><span>Pareto-optimal trips</span></div>
              <div><b>{visible.length}</b><span>after hard limits</span></div>
              <div><b>{res.stats.runtime_ms.toFixed(0)} ms</b><span>engine time</span></div>
              <div><b>{res.stats.labels_kept.toLocaleString()}</b><span>labels kept / {res.stats.labels_generated.toLocaleString()}</span></div>
            </div>
            {visible.length === 0 ? <p className="muted empty">Limits exclude every itinerary.</p> : (<>
              <div className="charts">
                <div className="panel"><h3>Trade-off view</h3><ScatterChart items={items} selected={selPos >= 0 ? selPos : null} onSelect={(i) => setSel(visible[i].idx)} x={sx} y={sy} setX={setSx} setY={setSy} /></div>
                <div className="panel"><h3>All five objectives <span className="muted">(top = better)</span></h3><ParallelCoords items={items} selected={selPos >= 0 ? selPos : null} onSelect={(i) => setSel(visible[i].idx)} /></div>
              </div>
              <h3>Ranked by your preferences</h3>
              <div className="list">
                {visible.slice(0, 30).map((v, i) => <ItineraryCard key={v.idx} it={v.it} rank={i + 1} active={v.idx === sel} onClick={() => setSel(v.idx === sel ? null : v.idx)} />)}
                {visible.length > 30 && <p className="muted">Showing top 30 of {visible.length}.</p>}
              </div>
            </>)}
          </>)}
        </section>
      </div>
    </main>
  );
}
