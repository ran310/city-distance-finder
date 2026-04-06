import { useCallback, useEffect, useId, useRef, useState } from "react";
import { fetchCities } from "../api";
import type { City } from "../types";

type Props = {
  label: string;
  value: City | null;
  onChange: (c: City | null) => void;
};

export function CityPicker({ label, value, onChange }: Props) {
  const listId = useId();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [items, setItems] = useState<City[]>([]);
  const wrapRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = useCallback(async (term: string) => {
    if (term.trim().length < 1) {
      setItems([]);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const rows = await fetchCities(term.trim());
      setItems(rows);
    } catch (e) {
      setItems([]);
      setErr(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runSearch(q);
    }, 260);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [q, runSearch]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, []);

  return (
    <div className="city-picker" ref={wrapRef}>
      <label className="field-label" htmlFor={listId + "-input"}>
        {label}
      </label>
      <div className="field-input-wrap">
        <input
          id={listId + "-input"}
          type="text"
          className="field-input"
          placeholder="Type a city or country…"
          value={value ? value.label : q}
          onChange={(e) => {
            onChange(null);
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId + "-listbox"}
          aria-autocomplete="list"
        />
        {value && (
          <button
            type="button"
            className="clear-btn"
            aria-label="Clear selection"
            onClick={() => {
              onChange(null);
              setQ("");
              setItems([]);
            }}
          >
            ×
          </button>
        )}
      </div>
      {open && !value && q.trim().length > 0 && (
        <ul className="dropdown" id={listId + "-listbox"} role="listbox">
          {loading && <li className="dropdown-meta">Searching…</li>}
          {err && <li className="dropdown-error">{err}</li>}
          {!loading && !err && items.length === 0 && (
            <li className="dropdown-meta">No matches</li>
          )}
          {items.map((c) => (
            <li key={c.id + c.label}>
              <button
                type="button"
                role="option"
                className="dropdown-item"
                onClick={() => {
                  onChange(c);
                  setOpen(false);
                  setQ("");
                }}
              >
                <span className="dropdown-item-title">{c.label}</span>
                <span className="dropdown-item-sub">
                  {c.lat.toFixed(2)}°, {c.lng.toFixed(2)}°
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
