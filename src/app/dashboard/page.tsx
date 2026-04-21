'use client';

import { useState, useEffect, useCallback } from 'react';
import DealCard from '@/components/dashboard/DealCard';
import AutomationPanel from '@/components/dashboard/AutomationPanel';
import AddPropertyForm from '@/components/dashboard/AddPropertyForm';
import type { TopDealSummary } from '@/types/real-estate';

export default function DashboardPage() {
  const [deals, setDeals] = useState<TopDealSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDeals = useCallback(async () => {
    const res = await fetch('/api/analyze');
    if (res.ok) {
      const data = (await res.json()) as { topDeals: TopDealSummary[] };
      setDeals(data.topDeals);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchDeals();
  }, [fetchDeals]);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Top Deals" value={deals.length} />
        <StatCard
          label="Total Spread"
          value={`$${(deals.reduce((s, d) => s + d.spread, 0) / 1000).toFixed(0)}K`}
        />
        <StatCard
          label="Dead Paper"
          value={deals.filter((d) => d.type === 'dead_paper').length}
          accent
        />
        <StatCard
          label="Avg Score"
          value={
            deals.length
              ? (deals.reduce((s, d) => s + d.score, 0) / deals.length).toFixed(1)
              : '—'
          }
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Top Deals */}
        <div className="xl:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-zinc-100 text-lg">Top Deals</h2>
            <AddPropertyForm onAdded={() => void fetchDeals()} />
          </div>

          {loading ? (
            <div className="text-zinc-500 text-sm">Loading…</div>
          ) : deals.length === 0 ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
              <p className="text-lg mb-1">No deals yet</p>
              <p className="text-sm">Add a property and run the automation scan to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {deals.map((deal) => (
                <DealCard key={deal.property.id} deal={deal} />
              ))}
            </div>
          )}
        </div>

        {/* Automation */}
        <div className="space-y-4">
          <h2 className="font-bold text-zinc-100 text-lg">Automation</h2>
          <AutomationPanel />

          {/* Module legend */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
            <p className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Active Modules</p>
            {[
              { n: 1, label: 'Buyer Intelligence', ready: true },
              { n: 2, label: 'Dead Paper Hunter', ready: true },
              { n: 3, label: 'OSINT Verification', ready: false },
              { n: 4, label: 'Deal Classifier', ready: true },
              { n: 5, label: 'Deal Analyzer', ready: true },
              { n: 6, label: 'Exit Match Engine', ready: true },
              { n: 7, label: 'Offer Engine', ready: true },
              { n: 8, label: 'Neo4j Graph', ready: false },
              { n: 9, label: 'Automation Loop', ready: true },
            ].map(({ n, label, ready }) => (
              <div key={n} className="flex items-center gap-2 text-sm">
                <span className={`h-2 w-2 rounded-full ${ready ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                <span className="text-zinc-400 w-4 text-xs">{n}</span>
                <span className={ready ? 'text-zinc-200' : 'text-zinc-500'}>{label}</span>
              </div>
            ))}
            <p className="text-xs text-zinc-600 pt-1">
              OSINT + Neo4j activate when env vars are set.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold ${accent ? 'text-cyan-400' : 'text-zinc-100'}`}>{value}</p>
    </div>
  );
}
