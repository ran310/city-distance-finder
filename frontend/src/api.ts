import type { City } from "./types";

/** Join Vite `base` (e.g. /city-distance-finder/) with /api/... for nginx path-prefix deploys. */
function apiUrl(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/?$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}/api${p}`.replace(/([^:]\/)\/+/g, "$1");
}

export async function fetchCities(q: string): Promise<City[]> {
  const params = new URLSearchParams({ q, limit: "150" });
  const res = await fetch(apiUrl(`/cities?${params}`));
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || res.statusText);
  }
  return data.cities as City[];
}

export async function fetchDistance(
  origin: Pick<City, "lat" | "lng">,
  destination: Pick<City, "lat" | "lng">
): Promise<{ kilometers: number; miles: number }> {
  const res = await fetch(apiUrl("/distance"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, destination }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || res.statusText);
  }
  return data;
}
