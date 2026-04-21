'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Property, DealType, DealStatus } from '@/types/real-estate';

const STATUS_COLS: { status: DealStatus; label: string; color: string }[] = [
  { status: 'new', label: 'New', color: 'border-zinc-600' },
  { status: 'investigating', label: 'Investigating', color: 'border-yellow-500/50' },
  { status: 'offer_ready', label: 'Offer Ready', color: 'border-cyan-500/50' },
  { status: 'offer_sent', label: 'Offer Sent', color: 'border-blue-500/50' },
  { status: 'under_contract', label: 'Under Contract', color: 'border-emerald-500/50' },
  { status: 'closed', label: 'Closed', color: 'border-emerald-400' },
];

const TYPE_DOT: Record<DealType, string> = {
  wholesale: 'bg-yellow-400',
  fix_and_flip: 'bg-orange-400',
  brrrr: 'bg-purple-400',
  dead_paper: 'bg-cyan-400',
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

export default function PipelinePage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchProperties = useCallback(async () => {
    const res = await fetch('/api/properties');
    if (res.ok) {
      const data = (await res.json()) as { properties: Property[] };
      setProperties(data.properties);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchProperties();
  }, [fetchProperties]);

  const byStatus = (status: DealStatus) => properties.filter((p) => p.dealStatus === status);

  if (loading) return <div className="text-zinc-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-4 max-w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Deal Pipeline</h1>
          <p className="text-sm text-zinc-500">{properties.length} properties tracked</p>
        </div>
      </div>

      <div className="overflow-x-auto pb-4">
        <div className="flex gap-4 min-w-max">
          {STATUS_COLS.map(({ status, label, color }) => {
            const items = byStatus(status);
            return (
              <div key={status} className="w-64">
                <div className={`border-t-2 ${color} pt-3 mb-3`}>
                  <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider">
                    {label}
                  </p>
                  <p className="text-xs text-zinc-600">{items.length} deals</p>
                </div>
                <div className="space-y-2">
                  {items.length === 0 ? (
                    <div className="bg-zinc-900/50 border border-dashed border-zinc-800 rounded-lg p-4 text-center text-xs text-zinc-600">
                      Empty
                    </div>
                  ) : (
                    items.map((p) => (
                      <div
                        key={p.id}
                        className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 space-y-2 hover:border-zinc-600 transition-colors"
                      >
                        <div className="flex items-start gap-2">
                          {p.dealType && (
                            <span className={`h-2 w-2 rounded-full mt-1 shrink-0 ${TYPE_DOT[p.dealType]}`} />
                          )}
                          <p className="text-xs font-medium text-zinc-200 leading-tight">{p.address}</p>
                        </div>
                        <div className="flex justify-between text-xs text-zinc-500">
                          <span>{p.zip}</span>
                          {p.listingPrice && <span>{fmt(p.listingPrice)}</span>}
                        </div>
                        {p.analysis?.spread != null && p.analysis.spread > 0 && (
                          <div className="text-xs text-emerald-400 font-medium">
                            Spread: {fmt(p.analysis.spread)}
                          </div>
                        )}
                        {p.exitMatch && (
                          <div className="text-xs text-cyan-400 truncate">
                            → {p.exitMatch.buyerName}
                          </div>
                        )}
                        <div className="text-xs text-zinc-600">
                          Score: {p.deadPaperScore}/6
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
