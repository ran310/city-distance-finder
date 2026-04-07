"""Build disambiguated display labels for city rows."""

from __future__ import annotations


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _state_display(state: str | None) -> str:
    s = (state or "").strip()
    return s if s else "—"


def assign_labels(rows: list[dict]) -> list[dict]:
    """
    rows: dicts with keys city, country, state (optional), plus id, lat, lng.

    Rules:
    - Use "City, State, Country" whenever the same city name appears more than once in the
      same country (different states), OR appears more than once in the result set globally
      (e.g. Paris TX vs Paris France) so state/region is always visible when it helps.
    - Otherwise: "City, Country"
    - Still duplicate labels after that: "1. City, State, Country", etc.
    """
    if not rows:
        return []

    # Count (city, country) pairs — multiple ⇒ same name in different states (or duplicates).
    cc_counts: dict[tuple[str, str], int] = {}
    for r in rows:
        k = (_norm(r.get("city")), _norm(r.get("country")))
        cc_counts[k] = cc_counts.get(k, 0) + 1

    # Same city name anywhere in this result (e.g. "Athens" US + "Athens" Greece).
    name_counts: dict[str, int] = {}
    for r in rows:
        n = _norm(r.get("city"))
        name_counts[n] = name_counts.get(n, 0) + 1

    provisional: list[tuple[dict, str]] = []
    for r in rows:
        city = (r.get("city") or "").strip() or "?"
        country = (r.get("country") or "").strip() or "?"
        state = r.get("state")
        k = (_norm(city), _norm(country))
        same_name_in_country = cc_counts[k] > 1
        same_name_in_results = name_counts[_norm(city)] > 1
        if same_name_in_country or same_name_in_results:
            label = f"{city}, {_state_display(state)}, {country}"
        else:
            label = f"{city}, {country}"
        provisional.append((r, label))

    # Numeric prefix for duplicate provisional labels (while preserving input order).
    label_totals: dict[str, int] = {}
    for _, label in provisional:
        label_totals[label] = label_totals.get(label, 0) + 1
    label_seen: dict[str, int] = {}
    out: list[dict] = []
    for r, label in provisional:
        total = label_totals[label]
        if total == 1:
            row = {**r, "label": label}
            out.append(row)
        else:
            label_seen[label] = label_seen.get(label, 0) + 1
            out.append({**r, "label": f"{label_seen[label]}. {label}"})
    return out
