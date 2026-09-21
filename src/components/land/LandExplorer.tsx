'use client';

import { useCallback, useState } from 'react';
import { LandMap } from './LandMap';
import { SoilBadge } from './SoilBadge';
import type { GeocodeResult, PowerLinesResult, SoilSuitabilityResult } from '@/lib/land/types';
import type { SearchedSite } from '@/lib/land/types';

type LoadState = 'idle' | 'loading' | 'error';

export function LandExplorer() {
  const [query, setQuery] = useState('');
  const [searchState, setSearchState] = useState<LoadState>('idle');
  const [searchResults, setSearchResults] = useState<GeocodeResult[]>([]);
  const [site, setSite] = useState<SearchedSite | null>(null);

  const [showPowerLines, setShowPowerLines] = useState(true);
  const [powerLines, setPowerLines] = useState<PowerLinesResult | null>(null);
  const [powerState, setPowerState] = useState<LoadState>('idle');

  const [soil, setSoil] = useState<SoilSuitabilityResult | null>(null);
  const [soilState, setSoilState] = useState<LoadState>('idle');

  const loadSiteData = useCallback(async (next: SearchedSite) => {
    setPowerState('loading');
    setSoilState('loading');
    setPowerLines(null);
    setSoil(null);

    const powerLinesPromise = fetch(
      `/api/land/power-lines?lat=${next.lat}&lon=${next.lon}&radiusM=750`,
    )
      .then((res) => {
        if (!res.ok) throw new Error('power-lines request failed');
        return res.json();
      })
      .then((data: PowerLinesResult) => {
        setPowerLines(data);
        setPowerState('idle');
      })
      .catch(() => setPowerState('error'));

    const soilPromise = fetch(`/api/land/soil?lat=${next.lat}&lon=${next.lon}`)
      .then((res) => {
        if (!res.ok) throw new Error('soil request failed');
        return res.json();
      })
      .then((data: SoilSuitabilityResult) => {
        setSoil(data);
        setSoilState('idle');
      })
      .catch(() => setSoilState('error'));

    await Promise.all([powerLinesPromise, soilPromise]);
  }, []);

  const runSearch = useCallback(async () => {
    if (!query.trim()) return;
    setSearchState('loading');
    setSearchResults([]);
    try {
      const res = await fetch(`/api/land/geocode?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('geocode request failed');
      const data: { results: GeocodeResult[] } = await res.json();
      setSearchResults(data.results);
      setSearchState('idle');
      if (data.results.length === 1) {
        const only = data.results[0];
        const next = { label: only.displayName, lat: only.lat, lon: only.lon };
        setSite(next);
        void loadSiteData(next);
      }
    } catch {
      setSearchState('error');
    }
  }, [query, loadSiteData]);

  const selectResult = useCallback(
    (result: GeocodeResult) => {
      const next = { label: result.displayName, lat: result.lat, lon: result.lon };
      setSite(next);
      setSearchResults([]);
      setQuery(result.displayName);
      void loadSiteData(next);
    },
    [loadSiteData],
  );

  return (
    <div className="flex h-full w-full">
      <aside className="flex w-96 flex-none flex-col gap-4 overflow-y-auto border-r border-white/10 bg-black/60 p-4">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">LAND INTELLIGENCE</h1>
          <p className="text-xs text-white/50">
            Address search · power-line overlay · soil/septic screen. Free, keyless public data.
          </p>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void runSearch();
          }}
          className="flex gap-2"
        >
          <input
            data-testid="search-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search an address or place"
            className="w-full rounded border border-white/20 bg-white/5 px-3 py-2 text-sm outline-none focus:border-sky-400"
          />
          <button
            type="submit"
            data-testid="search-button"
            className="rounded bg-sky-500 px-3 py-2 text-sm font-medium text-black hover:bg-sky-400"
          >
            Go
          </button>
        </form>

        {searchState === 'loading' && <p className="text-xs text-white/50">Searching…</p>}
        {searchState === 'error' && (
          <p data-testid="search-error" className="text-xs text-red-400">
            Search failed. Check your connection and try again.
          </p>
        )}

        {searchResults.length > 1 && (
          <ul data-testid="search-results" className="flex flex-col gap-1">
            {searchResults.map((result) => (
              <li key={`${result.lat}-${result.lon}`}>
                <button
                  type="button"
                  onClick={() => selectResult(result)}
                  className="w-full truncate rounded px-2 py-1 text-left text-sm hover:bg-white/10"
                  title={result.displayName}
                >
                  {result.displayName}
                </button>
              </li>
            ))}
          </ul>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            data-testid="power-lines-toggle"
            checked={showPowerLines}
            onChange={(event) => setShowPowerLines(event.target.checked)}
          />
          Power lines (OpenStreetMap)
        </label>

        {site && (
          <section className="flex flex-col gap-3 rounded border border-white/10 bg-white/5 p-3">
            <div>
              <h2 className="text-sm font-semibold">{site.label}</h2>
              <p className="text-xs text-white/50">
                {site.lat.toFixed(5)}, {site.lon.toFixed(5)}
              </p>
            </div>

            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-white/60">Power lines (750m)</h3>
              {powerState === 'loading' && <p className="text-xs text-white/50">Loading…</p>}
              {powerState === 'error' && (
                <p data-testid="power-error" className="text-xs text-red-400">
                  Lookup failed.
                </p>
              )}
              {powerState === 'idle' && powerLines && (
                <p data-testid="power-summary" className="text-xs">
                  {powerLines.lines.length} line segment(s), {powerLines.points.length} tower/pole/substation point(s)
                  mapped nearby.
                  {powerLines.lines.length === 0 && powerLines.points.length === 0 && (
                    <span className="text-white/50"> No power infrastructure mapped in OSM near this point — absence here is not proof none exists.</span>
                  )}
                </p>
              )}
            </div>

            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-white/60">Soil / septic screen</h3>
              {soilState === 'loading' && <p className="text-xs text-white/50">Loading…</p>}
              {soilState === 'error' && (
                <p data-testid="soil-error" className="text-xs text-red-400">
                  Lookup failed.
                </p>
              )}
              {soilState === 'idle' && soil && (
                <div className="flex flex-col gap-1" data-testid="soil-result">
                  <SoilBadge suitability={soil.suitability} />
                  <p className="text-xs text-white/70">{soil.reason}</p>
                  <p className="text-[11px] text-white/40">
                    Screening only, from USDA SSURGO data — not a substitute for a permitted percolation test.
                  </p>
                </div>
              )}
            </div>
          </section>
        )}
      </aside>

      <main className="relative flex-1">
        <LandMap site={site} powerLines={powerLines} showPowerLines={showPowerLines} />
      </main>
    </div>
  );
}
