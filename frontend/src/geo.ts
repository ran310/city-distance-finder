/** LatLng as [lat, lng] for Leaflet */
export type LatLngTuple = [number, number];

const D2R = Math.PI / 180;

/**
 * Spherical interpolation along a great circle (slerp on the sphere).
 */
export function greatCirclePoints(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
  segments = 80
): LatLngTuple[] {
  const phi1 = lat1 * D2R;
  const lam1 = lng1 * D2R;
  const phi2 = lat2 * D2R;
  const lam2 = lng2 * D2R;

  const ax = Math.cos(phi1) * Math.cos(lam1);
  const ay = Math.cos(phi1) * Math.sin(lam1);
  const az = Math.sin(phi1);
  const bx = Math.cos(phi2) * Math.cos(lam2);
  const by = Math.cos(phi2) * Math.sin(lam2);
  const bz = Math.sin(phi2);

  const omega = Math.acos(Math.min(1, Math.max(-1, ax * bx + ay * by + az * bz)));
  if (!Number.isFinite(omega) || omega < 1e-8) {
    return [[lat1, lng1]];
  }

  const out: LatLngTuple[] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const s0 = Math.sin((1 - t) * omega);
    const s1 = Math.sin(t * omega);
    const x = (s0 * ax + s1 * bx) / Math.sin(omega);
    const y = (s0 * ay + s1 * by) / Math.sin(omega);
    const z = (s0 * az + s1 * bz) / Math.sin(omega);
    const lat = Math.atan2(z, Math.hypot(x, y)) / D2R;
    let lng = Math.atan2(y, x) / D2R;
    if (lng > 180) lng -= 360;
    if (lng < -180) lng += 360;
    out.push([lat, lng]);
  }
  return out;
}

/**
 * Shift longitudes by ±360° so each step moves the short way on the map (≤180°).
 * Without this, routes like Delhi ↔ Seattle draw the long way around the globe or
 * jump off-screen at the antimeridian.
 */
export function unwrapLongitudePath(points: LatLngTuple[]): LatLngTuple[] {
  if (points.length === 0) return [];
  const out: LatLngTuple[] = [[points[0]![0], points[0]![1]]];
  let prevLng = points[0]![1];
  for (let i = 1; i < points.length; i++) {
    const lat = points[i]![0];
    let lng = points[i]![1];
    let delta = lng - prevLng;
    while (delta > 180) {
      lng -= 360;
      delta = lng - prevLng;
    }
    while (delta < -180) {
      lng += 360;
      delta = lng - prevLng;
    }
    out.push([lat, lng]);
    prevLng = lng;
  }
  return out;
}

export function bearingDeg(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const y = Math.sin((lng2 - lng1) * D2R) * Math.cos(lat2 * D2R);
  const x =
    Math.cos(lat1 * D2R) * Math.sin(lat2 * D2R) -
    Math.sin(lat1 * D2R) * Math.cos(lat2 * D2R) * Math.cos((lng2 - lng1) * D2R);
  return (Math.atan2(y, x) / D2R + 360) % 360;
}

const EARTH_KM = 6371.0088;

/** Great-circle distance in km (matches server haversine). */
export function haversineKm(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const p1 = lat1 * D2R;
  const p2 = lat2 * D2R;
  const dphi = (lat2 - lat1) * D2R;
  const dlmb = (lng2 - lng1) * D2R;
  const a =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dlmb / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Leaflet zoom hints from route length (km). */
export function zoomForDistanceKm(km: number): { flyOrigin: number; fitMax: number } {
  const d = Math.max(km, 0.5);
  if (d < 30) return { flyOrigin: 11, fitMax: 12 };
  if (d < 100) return { flyOrigin: 10, fitMax: 11 };
  if (d < 250) return { flyOrigin: 9, fitMax: 10 };
  if (d < 600) return { flyOrigin: 8, fitMax: 9 };
  if (d < 1500) return { flyOrigin: 7, fitMax: 8 };
  if (d < 3500) return { flyOrigin: 6, fitMax: 7 };
  if (d < 8000) return { flyOrigin: 5, fitMax: 6 };
  if (d < 14000) return { flyOrigin: 4, fitMax: 5 };
  return { flyOrigin: 3, fitMax: 4 };
}
