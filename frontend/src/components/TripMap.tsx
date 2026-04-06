import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  useMap,
} from "react-leaflet";
import {
  bearingDeg,
  greatCirclePoints,
  haversineKm,
  unwrapLongitudePath,
  zoomForDistanceKm,
  type LatLngTuple,
} from "../geo";
import type { City } from "../types";

const cartoDark =
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";

function sleep(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

function arrowIcon(angle: number) {
  return L.divIcon({
    className: "arrow-leaflet-icon",
    html: `<div class="arrow-glyph" style="transform:rotate(${angle}deg)">➤</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function distanceBadgeIcon(mi: number, km: number) {
  const miStr = mi.toLocaleString(undefined, {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  });
  const kmStr = km.toLocaleString(undefined, {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  });
  return L.divIcon({
    className: "route-distance-badge",
    html: `<div class="route-distance-inner"><span class="rd-mi">${miStr} mi</span><span class="rd-sep">·</span><span class="rd-km">${kmStr} km</span></div>`,
    iconSize: [1, 1],
    iconAnchor: [0, 0],
  });
}

function IdleView({ show }: { show: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (show) {
      map.setView([18, 12], 2, { animate: true, duration: 0.55 });
    }
  }, [show, map]);
  return null;
}

function RouteSequence({
  origin,
  dest,
  runId,
  distance,
}: {
  origin: City;
  dest: City;
  runId: number;
  distance: { km: number; mi: number } | null;
}) {
  const map = useMap();
  const path = useMemo(
    () => greatCirclePoints(origin.lat, origin.lng, dest.lat, dest.lng, 100),
    [origin, dest]
  );

  /** Same route with longitudes unwrapped so the line stays on one continuous map strip. */
  const mapPath = useMemo(() => unwrapLongitudePath(path), [path]);

  const km =
    distance?.km ??
    haversineKm(origin.lat, origin.lng, dest.lat, dest.lng);
  const mi = distance?.mi ?? km * 0.621371;
  const { flyOrigin, fitMax } = zoomForDistanceKm(km);

  const labelPosition = useMemo((): LatLngTuple => {
    if (mapPath.length === 0) return [origin.lat, origin.lng];
    return mapPath[Math.floor(mapPath.length / 2)]!;
  }, [mapPath, origin.lat, origin.lng]);

  const [originDot, setOriginDot] = useState(false);
  const [destDot, setDestDot] = useState(false);
  const [showLine, setShowLine] = useState(false);
  const [arrowPos, setArrowPos] = useState<LatLngTuple | null>(null);
  const [arrowAngle, setArrowAngle] = useState(0);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    setOriginDot(false);
    setDestDot(false);
    setShowLine(false);
    setArrowPos(null);

    const run = async () => {
      map.invalidateSize();
      map.setView([16, 8], 2, { animate: true, duration: 0.55 });
      await sleep(650);
      if (cancelled.current) return;

      map.flyTo([origin.lat, origin.lng], flyOrigin, { duration: 1.45 });
      await sleep(1700);
      if (cancelled.current) return;
      setOriginDot(true);

      const b = L.latLngBounds(mapPath.map(([lat, lng]) => [lat, lng] as [number, number]));
      map.flyToBounds(b, { padding: [110, 110], duration: 1.3, maxZoom: fitMax });
      await sleep(1500);
      if (cancelled.current) return;
      setDestDot(true);

      await sleep(350);
      if (cancelled.current) return;
      setShowLine(true);

      for (let i = 0; i < mapPath.length; i++) {
        if (cancelled.current) return;
        const cur = mapPath[i]!;
        const nxt = mapPath[Math.min(i + 1, mapPath.length - 1)]!;
        setArrowPos(cur);
        setArrowAngle(bearingDeg(cur[0], cur[1], nxt[0], nxt[1]));
        await sleep(18);
      }
    };

    run();
    return () => {
      cancelled.current = true;
    };
  }, [origin, dest, map, mapPath, runId, flyOrigin, fitMax]);

  const linePositions = mapPath.map(([la, lo]) => L.latLng(la, lo));
  const routeStart = mapPath[0]!;
  const routeEnd = mapPath[mapPath.length - 1]!;

  return (
    <>
      {originDot && (
        <CircleMarker
          center={routeStart}
          radius={9}
          pathOptions={{
            color: "#5eead4",
            fillColor: "#14b8a6",
            fillOpacity: 0.95,
            weight: 3,
          }}
        />
      )}
      {destDot && (
        <CircleMarker
          center={routeEnd}
          radius={9}
          pathOptions={{
            color: "#fda4af",
            fillColor: "#fb7185",
            fillOpacity: 0.95,
            weight: 3,
          }}
        />
      )}
      {showLine && (
        <Polyline
          positions={linePositions}
          pathOptions={{
            color: "#fbbf24",
            weight: 3,
            opacity: 0.92,
            dashArray: "10 14",
            lineCap: "round",
            lineJoin: "round",
          }}
        />
      )}
      {showLine && (
        <Marker
          position={labelPosition}
          icon={distanceBadgeIcon(mi, km)}
          zIndexOffset={800}
        />
      )}
      {showLine && arrowPos && (
        <Marker position={arrowPos} icon={arrowIcon(arrowAngle)} zIndexOffset={900} />
      )}
    </>
  );
}

type Props = {
  origin: City | null;
  dest: City | null;
  activeRun: number;
  distance: { km: number; mi: number } | null;
};

export function TripMap({ origin, dest, activeRun, distance }: Props) {
  const ready = origin && dest;

  return (
    <div className="map-shell">
      <MapContainer
        className="map-canvas"
        center={[18, 12]}
        zoom={2}
        minZoom={2}
        maxZoom={18}
        maxBounds={[
          [-85, -1000],
          [85, 1000],
        ]}
        maxBoundsViscosity={0.85}
        scrollWheelZoom
        worldCopyJump
      >
        <TileLayer attribution="&copy; OpenStreetMap &copy; CARTO" url={cartoDark} />
        <IdleView show={!ready} />
        {ready && (
          <RouteSequence
            key={activeRun}
            origin={origin}
            dest={dest}
            runId={activeRun}
            distance={distance}
          />
        )}
      </MapContainer>
      {!ready && (
        <div className="map-placeholder">
          <p>Select two cities and press <strong>Go</strong> to fly the route.</p>
        </div>
      )}
    </div>
  );
}
