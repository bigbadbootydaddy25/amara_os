'use client';

import type { TopDealSummary } from '@/types/real-estate';

const TYPE_COLORS: Record<string, string> = {
  wholesale: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30',
  fix_and_flip: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
  brrrr: 'text-purple-400 bg-purple-400/10 border-purple-400/30',
  dead_paper: 'text-cyan-400 bg-cyan-400/10 border-cyan-400/30',
};

const TYPE_LABELS: Record<string, string> = {
  wholesale: 'WHOLESALE',
  fix_and_flip: 'FIX & FLIP',
  brrrr: 'BRRRR',
  dead_paper: 'DEAD PAPER',
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

export default function DealCard({ deal }: { deal: TopDealSummary }) {
  const colorClass = TYPE_COLORS[deal.type] ?? TYPE_COLORS.wholesale;
  const label = TYPE_LABELS[deal.type] ?? deal.type;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex flex-col gap-3 hover:border-zinc-600 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold text-zinc-100 truncate">{deal.property.address}</p>
          <p className="text-xs text-zinc-500">
            {deal.property.city}, {deal.property.state} {deal.property.zip}
          </p>
        </div>
        <span className={`text-xs font-bold px-2 py-0.5 rounded border shrink-0 ${colorClass}`}>
          {label}
        </span>
      </div>

      {/* Score */}
      <div className="flex gap-1 items-center">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 w-6 rounded-full ${
              i < deal.score ? 'bg-cyan-400' : 'bg-zinc-700'
            }`}
          />
        ))}
        <span className="text-xs text-zinc-500 ml-1">score {deal.score}/6</span>
      </div>

      {/* Financials */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-zinc-800/60 rounded-lg p-2">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">ARV / Value</p>
          <p className="text-sm font-bold text-zinc-100">{fmt(deal.arvOrValue)}</p>
        </div>
        <div className="bg-zinc-800/60 rounded-lg p-2">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Cost / MAO</p>
          <p className="text-sm font-bold text-zinc-100">{fmt(deal.cost)}</p>
        </div>
        <div className="bg-zinc-800/60 rounded-lg p-2">
          <p className="text-xs text-zinc-500 uppercase tracking-wider">Spread</p>
          <p className={`text-sm font-bold ${deal.spread >= 100_000 ? 'text-cyan-400' : 'text-emerald-400'}`}>
            {fmt(deal.spread)}
          </p>
        </div>
      </div>

      {/* Exit buyer */}
      {deal.exitBuyer && (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-500">Exit buyer:</span>
          <span className="text-cyan-300 font-medium">{deal.exitBuyer}</span>
        </div>
      )}

      {/* Status */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-500 capitalize">{deal.property.dealStatus.replace(/_/g, ' ')}</span>
        {deal.property.offerTerms && (
          <span className="text-emerald-400">
            Offer: {fmt(deal.property.offerTerms.offerPrice)} · {deal.property.offerTerms.closingDays}d close
          </span>
        )}
      </div>
    </div>
  );
}
