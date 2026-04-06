import { useCallback, useState } from "react";
import { fetchDistance } from "./api";
import { CityPicker } from "./components/CityPicker";
import { TripMap } from "./components/TripMap";
import type { City } from "./types";

export default function App() {
  const [source, setSource] = useState<City | null>(null);
  const [dest, setDest] = useState<City | null>(null);
  const [run, setRun] = useState(0);
  const [tripActive, setTripActive] = useState(false);
  const [dist, setDist] = useState<{ km: number; mi: number } | null>(null);
  const [distErr, setDistErr] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const onGo = useCallback(async () => {
    if (!source || !dest) return;
    setPending(true);
    setDistErr(null);
    setDist(null);
    try {
      const d = await fetchDistance(source, dest);
      setDist({ km: d.kilometers, mi: d.miles });
    } catch (e) {
      setDistErr(e instanceof Error ? e.message : "Could not compute distance");
    } finally {
      setPending(false);
    }
    setTripActive(true);
    setRun((r) => r + 1);
  }, [source, dest]);

  const onReset = () => {
    setTripActive(false);
    setDist(null);
    setDistErr(null);
    setSource(null);
    setDest(null);
    setRun((r) => r + 1);
  };

  return (
    <div className="app">
      <div className="bg-grid" aria-hidden />
      <header className="hero">
        <p className="eyebrow">Iceberg · geolocation</p>
        <h1>City distance explorer</h1>
        <p className="lede">
          Search by city or country, pick two places, then watch the great-circle path
          unfold on the map.
        </p>
      </header>

      <div className="layout">
        <section className="panel glass">
          <div className="panel-grid">
            <CityPicker label="Source" value={source} onChange={setSource} />
            <CityPicker label="Destination" value={dest} onChange={setDest} />
          </div>
          <div className="actions">
            <button
              type="button"
              className="btn primary"
              disabled={!source || !dest || pending}
              onClick={onGo}
            >
              {pending ? "Working…" : "Go"}
            </button>
            <button type="button" className="btn ghost" onClick={onReset}>
              Reset
            </button>
          </div>
          {(dist || distErr) && (
            <div className="distance-card">
              {distErr && <p className="distance-error">{distErr}</p>}
              {dist && (
                <>
                  <p className="distance-label">Great-circle distance</p>
                  <div className="distance-values">
                    <div>
                      <span className="mono">{dist.mi.toLocaleString()}</span>
                      <span className="unit">miles</span>
                    </div>
                    <div className="sep" />
                    <div>
                      <span className="mono">{dist.km.toLocaleString()}</span>
                      <span className="unit">kilometers</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </section>

        <section className="map-panel glass">
          <TripMap
            origin={tripActive ? source : null}
            dest={tripActive ? dest : null}
            activeRun={run}
            distance={tripActive ? dist : null}
          />
        </section>
      </div>
    </div>
  );
}
