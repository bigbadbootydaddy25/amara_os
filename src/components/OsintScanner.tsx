'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useOsintStore } from '@/stores/osint-store';
import type { OsintScanResult } from '@/types';

function formatCoord(val: number | undefined): string {
  if (val === undefined) return '—';
  return val.toFixed(5);
}

function ScanResultView({ result }: { result: OsintScanResult }) {
  const { location, network, place, queryType, query, timestamp } = result;
  const ts = new Date(timestamp).toLocaleTimeString();

  return (
    <div className="space-y-3 font-mono text-[11px]">
      <div className="flex items-baseline justify-between border-b border-cyan-400/15 pb-2">
        <span className="text-[10px] uppercase tracking-[0.3em] text-cyan-400/60">
          {queryType} scan
        </span>
        <span className="text-white/30">{ts}</span>
      </div>

      <Row label="TARGET" value={query} />

      {location && (
        <section>
          <div className="mb-1 text-[9px] uppercase tracking-[0.4em] text-cyan-300/40">
            Location
          </div>
          {location.displayName && (
            <Row label="DISPLAY" value={location.displayName} truncate />
          )}
          {(location.lat !== undefined || location.lon !== undefined) && (
            <Row
              label="COORDS"
              value={`${formatCoord(location.lat)}, ${formatCoord(location.lon)}`}
            />
          )}
          <Row label="CITY" value={location.city} />
          <Row label="REGION" value={location.region} />
          <Row label="COUNTRY" value={location.country} flag={location.countryCode} />
          <Row label="ZIP" value={location.zip} />
          <Row label="TIMEZONE" value={location.timezone} />
          <Row label="CONTINENT" value={location.continent} />
        </section>
      )}

      {network && (
        <section>
          <div className="mb-1 text-[9px] uppercase tracking-[0.4em] text-cyan-300/40">
            Network
          </div>
          <Row label="ISP" value={network.isp} />
          <Row label="ORG" value={network.org} />
          <Row label="ASN" value={network.as} />
          <Row label="AS NAME" value={network.asName} />
          {network.isProxy && <Flag label="PROXY DETECTED" />}
          {network.isHosting && <Flag label="HOSTING / DATACENTER" />}
        </section>
      )}

      {place && (
        <section>
          <div className="mb-1 text-[9px] uppercase tracking-[0.4em] text-cyan-300/40">
            Place
          </div>
          <Row label="TYPE" value={place.type} />
          <Row label="CATEGORY" value={place.category} />
          <Row label="OSM TYPE" value={place.osmType} />
          {place.osmId !== undefined && (
            <Row label="OSM ID" value={String(place.osmId)} />
          )}
          {place.importance !== undefined && (
            <Row label="IMPORTANCE" value={place.importance.toFixed(4)} />
          )}
        </section>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  flag,
  truncate,
}: {
  label: string;
  value: string | undefined;
  flag?: string;
  truncate?: boolean;
}) {
  if (!value) return null;

  return (
    <div className="flex gap-2 leading-5">
      <span className="w-20 shrink-0 text-white/30">{label}</span>
      <span
        className={`text-cyan-100/80 ${truncate ? 'overflow-hidden text-ellipsis whitespace-nowrap' : 'break-all'}`}
      >
        {flag ? `${flag} ` : ''}
        {value}
      </span>
    </div>
  );
}

function Flag({ label }: { label: string }) {
  return (
    <div className="mt-0.5 inline-flex items-center gap-1.5 rounded border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.25em] text-amber-300/80">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400/70" />
      {label}
    </div>
  );
}

function HistoryItem({
  result,
  onSelect,
}: {
  result: OsintScanResult;
  onSelect: (r: OsintScanResult) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(result)}
      className="w-full truncate rounded px-2 py-1 text-left font-mono text-[10px] text-white/40 transition-colors hover:bg-white/5 hover:text-cyan-300/70"
    >
      <span className="mr-2 text-white/20">{result.queryType.slice(0, 2).toUpperCase()}</span>
      {result.query}
    </button>
  );
}

export function OsintScanner() {
  const isOpen = useOsintStore((s) => s.isOpen);
  const isScanning = useOsintStore((s) => s.isScanning);
  const result = useOsintStore((s) => s.result);
  const error = useOsintStore((s) => s.error);
  const history = useOsintStore((s) => s.history);
  const { setOpen, setScanning, setResult, setError, pushHistory } = useOsintStore.getState();

  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const close = useCallback(() => {
    setOpen(false);
  }, [setOpen]);

  const runScan = useCallback(
    async (target: string) => {
      const q = target.trim();
      if (!q || isScanning) return;

      setScanning(true);
      setError(null);
      setResult(null);

      try {
        const res = await fetch('/api/osint/land', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q }),
        });

        const data = (await res.json()) as OsintScanResult & { error?: string };

        if (!res.ok || data.error) {
          setError(data.error ?? 'Scan failed');
          return;
        }

        setResult(data);
        pushHistory(data);
      } catch {
        setError('Network error — unable to reach scanner');
      } finally {
        setScanning(false);
      }
    },
    [isScanning, pushHistory, setError, setResult, setScanning],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      void runScan(query);
    },
    [query, runScan],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
        return;
      }

      if (
        e.key.toLowerCase() === 'o' &&
        !e.ctrlKey &&
        !e.metaKey &&
        !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName ?? '')
      ) {
        setOpen(true);
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [close, setOpen]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-8 right-8 z-30 flex items-center gap-2 rounded-full border border-cyan-400/20 bg-black/40 px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.4em] text-cyan-300/40 backdrop-blur-sm transition-all duration-200 hover:border-cyan-400/40 hover:text-cyan-300/70"
        title="Open OSINT Land Scanner (O)"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-cyan-400/50" />
        OSINT
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />

      <div className="relative z-10 flex h-full max-h-[640px] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-cyan-400/15 bg-black/85 shadow-[0_0_60px_rgba(0,212,255,0.06)] backdrop-blur-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inset-0 rounded-full ${isScanning ? 'animate-ping bg-cyan-400/60' : 'bg-cyan-400/30'}`}
              />
              <span
                className={`relative rounded-full ${isScanning ? 'bg-cyan-400' : 'bg-cyan-400/50'}`}
              />
            </span>
            <span className="font-mono text-[11px] uppercase tracking-[0.45em] text-cyan-300/70">
              OSINT Land Scanner
            </span>
          </div>
          <button
            type="button"
            onClick={close}
            className="font-mono text-[10px] text-white/20 transition-colors hover:text-white/50"
            aria-label="Close"
          >
            ESC
          </button>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="border-b border-white/5 px-5 py-3">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="IP address, coordinates, or place name…"
              className="min-w-0 flex-1 rounded-lg border border-white/8 bg-white/4 px-3 py-2 font-mono text-[12px] text-cyan-100/80 placeholder-white/20 outline-none transition-colors focus:border-cyan-400/30 focus:bg-white/6"
              disabled={isScanning}
              autoComplete="off"
              spellCheck={false}
            />
            <button
              type="submit"
              disabled={isScanning || !query.trim()}
              className="rounded-lg border border-cyan-400/25 bg-cyan-400/8 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.3em] text-cyan-300/70 transition-all duration-150 hover:border-cyan-400/45 hover:bg-cyan-400/15 hover:text-cyan-200 disabled:opacity-30"
            >
              {isScanning ? 'Scanning…' : 'Scan'}
            </button>
          </div>
          <p className="mt-1.5 font-mono text-[9px] text-white/18 tracking-[0.2em]">
            Accepts IPv4 addresses · decimal coordinates (lat,lon) · place names
          </p>
        </form>

        {/* Body */}
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {error && (
            <div className="m-4 rounded-lg border border-red-400/20 bg-red-400/8 px-4 py-3 font-mono text-[11px] text-red-300/70">
              {error}
            </div>
          )}

          {result && (
            <div className="p-5">
              <ScanResultView result={result} />
            </div>
          )}

          {!result && !error && !isScanning && history.length === 0 && (
            <div className="flex flex-1 items-center justify-center">
              <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-white/15">
                Awaiting target
              </p>
            </div>
          )}

          {isScanning && (
            <div className="flex flex-1 items-center justify-center">
              <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-cyan-300/40">
                Scanning…
              </p>
            </div>
          )}

          {history.length > 0 && (
            <div className="border-t border-white/5 px-3 py-2">
              <p className="mb-1 px-2 font-mono text-[9px] uppercase tracking-[0.4em] text-white/20">
                History
              </p>
              {history.map((r) => (
                <HistoryItem
                  key={`${r.timestamp}-${r.query}`}
                  result={r}
                  onSelect={(r) => {
                    setResult(r);
                    setQuery(r.query);
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
