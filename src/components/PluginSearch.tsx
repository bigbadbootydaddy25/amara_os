'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import type { Plugin } from '@/types';

const CATEGORIES = ['All', 'Productivity', 'Smart Home', 'Entertainment', 'Communication', 'Utilities', 'Health', 'Finance'];

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <svg
          key={star}
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill={star <= Math.round(rating) ? '#00d4ff' : 'none'}
          stroke={star <= Math.round(rating) ? '#00d4ff' : '#ffffff30'}
          strokeWidth="1"
          aria-hidden="true"
        >
          <polygon points="5,1 6.2,3.8 9.5,4.1 7.1,6.3 7.9,9.5 5,7.8 2.1,9.5 2.9,6.3 0.5,4.1 3.8,3.8" />
        </svg>
      ))}
      <span className="ml-0.5 text-[10px] font-mono text-white/50">{rating.toFixed(1)}</span>
    </span>
  );
}

function formatInstalls(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function PluginCard({ plugin, installed, onToggle }: {
  plugin: Plugin;
  installed: boolean;
  onToggle: (id: string) => void;
}) {
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-white/8 bg-white/3 p-4 backdrop-blur-sm transition-colors duration-200 hover:border-cyan-400/20 hover:bg-white/5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-white/90">{plugin.name}</h3>
          <p className="mt-0.5 text-[11px] font-mono text-white/40">{plugin.author} · v{plugin.version}</p>
        </div>
        <button
          type="button"
          onClick={() => onToggle(plugin.id)}
          className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-mono uppercase tracking-widest transition-colors duration-200 ${
            installed
              ? 'border-cyan-400/30 bg-cyan-400/10 text-cyan-300 hover:border-red-400/30 hover:bg-red-400/10 hover:text-red-300'
              : 'border-white/15 bg-white/5 text-white/60 hover:border-cyan-400/40 hover:bg-cyan-400/10 hover:text-cyan-300'
          }`}
        >
          {installed ? 'Installed' : 'Install'}
        </button>
      </div>

      <p className="text-[12px] leading-relaxed text-white/55">{plugin.description}</p>

      <div className="flex items-center justify-between gap-2">
        <StarRating rating={plugin.rating} />
        <span className="text-[10px] font-mono text-white/35">{formatInstalls(plugin.installs)} installs</span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[9px] font-mono uppercase tracking-widest text-white/40">
          {plugin.category}
        </span>
        {plugin.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-white/8 px-2 py-0.5 text-[9px] font-mono text-white/30"
          >
            {tag}
          </span>
        ))}
      </div>
    </article>
  );
}

export function PluginSearch() {
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPlugins = useCallback(async (q: string, category: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set('q', q);
      if (category !== 'All') params.set('category', category);
      const res = await fetch(`/api/plugins?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch plugins');
      const data = (await res.json()) as { plugins: Plugin[]; total: number };
      setPlugins(data.plugins);
      setTotal(data.total);
    } catch {
      setPlugins([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void fetchPlugins(query, activeCategory);
    }, 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, activeCategory, fetchPlugins]);

  const toggleInstall = (id: string) => {
    setInstalled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#0a0a0f]">
      {/* Background gradient */}
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(0,212,255,0.06),transparent_55%)]" aria-hidden="true" />

      {/* Header */}
      <header className="relative z-10 flex shrink-0 items-center justify-between border-b border-white/6 px-6 py-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest text-white/50 transition-colors hover:border-white/20 hover:text-white/70"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
              <path d="M7 1L3 5L7 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Back
          </Link>
          <div>
            <h1 className="text-sm font-semibold tracking-widest text-white/80">AMARA Plugin Store</h1>
            <p className="text-[10px] font-mono text-white/35">Extend your AI experience</p>
          </div>
        </div>
        <div className="text-[10px] font-mono text-white/30">
          {installed.size > 0 && (
            <span className="rounded-full border border-cyan-400/25 bg-cyan-400/8 px-2 py-1 text-cyan-300/70">
              {installed.size} installed
            </span>
          )}
        </div>
      </header>

      {/* Search bar */}
      <div className="relative z-10 shrink-0 border-b border-white/6 px-6 py-4">
        <div className="relative">
          <svg
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/30"
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.25" />
            <path d="M9.5 9.5L12.5 12.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search plugins…"
            className="w-full rounded-xl border border-white/10 bg-white/4 py-2.5 pl-9 pr-4 text-sm text-white/80 placeholder-white/25 outline-none transition-colors focus:border-cyan-400/30 focus:bg-white/6"
          />
        </div>
      </div>

      {/* Category filters */}
      <div className="relative z-10 shrink-0 overflow-x-auto border-b border-white/6 px-6 py-3">
        <div className="flex gap-2" role="group" aria-label="Filter by category">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`shrink-0 rounded-full border px-3 py-1 text-[10px] font-mono uppercase tracking-widest transition-colors duration-150 ${
                activeCategory === cat
                  ? 'border-cyan-400/40 bg-cyan-400/12 text-cyan-300'
                  : 'border-white/10 bg-transparent text-white/40 hover:border-white/20 hover:text-white/60'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Results count */}
      <div className="relative z-10 shrink-0 px-6 py-2">
        <p className="text-[10px] font-mono text-white/30">
          {loading ? 'Searching…' : `${total} plugin${total !== 1 ? 's' : ''} found`}
        </p>
      </div>

      {/* Plugin grid */}
      <div className="relative z-10 min-h-0 flex-1 overflow-y-auto px-6 pb-8">
        {loading ? (
          <div className="flex h-32 items-center justify-center">
            <span className="text-[11px] font-mono text-white/30 animate-pulse">Loading…</span>
          </div>
        ) : plugins.length === 0 ? (
          <div className="flex h-32 flex-col items-center justify-center gap-2">
            <span className="text-2xl text-white/15">⊘</span>
            <span className="text-[11px] font-mono text-white/30">No plugins match your search</span>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plugins.map((plugin) => (
              <PluginCard
                key={plugin.id}
                plugin={plugin}
                installed={installed.has(plugin.id)}
                onToggle={toggleInstall}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
