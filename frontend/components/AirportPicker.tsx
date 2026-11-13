"use client";
import { useId, useMemo, useState } from "react";
import type { Airport } from "@/lib/api";
import { airportLabel, searchAirports } from "@/lib/search";

type Props = { label: string; airports: Airport[]; value: string; onChange: (code: string) => void; placeholder?: string };

/** Autocomplete for airports: type a city, country, airport name, IATA code or Chinese name. */
export default function AirportPicker({ label, airports, value, onChange, placeholder }: Props) {
  const id = useId();
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const selected = airports.find((a) => a.code === value);
  const results = useMemo(() => searchAirports(airports, text), [airports, text]);

  const choose = (a: Airport) => { onChange(a.code); setEditing(false); setOpen(false); setText(""); };

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { if (open && results[active]) { e.preventDefault(); choose(results[active]); } }
    else if (e.key === "Escape") { setOpen(false); setEditing(false); setText(""); (e.target as HTMLInputElement).blur(); }
  }

  return (
    <div className="picker">
      <label htmlFor={`${id}-in`}>{label}</label>
      <input
        id={`${id}-in`} type="text" autoComplete="off" spellCheck={false}
        role="combobox" aria-expanded={open} aria-controls={`${id}-list`} aria-autocomplete="list"
        aria-activedescendant={open && results[active] ? `${id}-o${active}` : undefined}
        placeholder={placeholder ?? "City, country or airport"}
        value={editing ? text : selected ? airportLabel(selected) : ""}
        onFocus={(e) => { setEditing(true); setText(""); setOpen(true); setActive(0); e.currentTarget.select(); }}
        onBlur={() => { setEditing(false); setOpen(false); setText(""); }}
        onChange={(e) => { setText(e.target.value); setOpen(true); setActive(0); }}
        onKeyDown={onKey}
      />
      {open && (
        <ul id={`${id}-list`} role="listbox" aria-label={`${label} suggestions`} className="suggest">
          {!text && <li className="suggest-head" role="presentation">Popular airports</li>}
          {results.map((a, i) => (
            <li
              key={a.code} id={`${id}-o${i}`} role="option" aria-selected={i === active}
              className={i === active ? "opt active" : "opt"}
              onMouseDown={(e) => { e.preventDefault(); choose(a); }} onMouseEnter={() => setActive(i)}
            >
              <span className="code">{a.code}</span>
              <span className="what"><span><b>{a.city}</b>, {a.country}</span><small>{a.name}</small></span>
            </li>
          ))}
          {text && results.length === 0 && <li className="none" role="presentation">No match. Try a city, country, airport name or code.</li>}
        </ul>
      )}
    </div>
  );
}
