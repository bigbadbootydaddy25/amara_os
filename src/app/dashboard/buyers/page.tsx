'use client';

import { useState, useEffect, useCallback } from 'react';
import AddBuyerForm from '@/components/dashboard/AddBuyerForm';
import type { Buyer } from '@/types/real-estate';

const TYPE_COLORS: Record<string, string> = {
  builder: 'text-cyan-400 bg-cyan-400/10',
  flipper: 'text-orange-400 bg-orange-400/10',
  landlord: 'text-purple-400 bg-purple-400/10',
  developer: 'text-emerald-400 bg-emerald-400/10',
  wholesaler: 'text-yellow-400 bg-yellow-400/10',
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

export default function BuyersPage() {
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  const fetchBuyers = useCallback(async () => {
    const res = await fetch('/api/buyers');
    if (res.ok) {
      const data = (await res.json()) as { buyers: Buyer[] };
      setBuyers(data.buyers);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void fetchBuyers();
  }, [fetchBuyers]);

  const deleteBuyer = async (id: string) => {
    await fetch(`/api/buyers?id=${id}`, { method: 'DELETE' });
    await fetchBuyers();
  };

  const filtered = buyers.filter(
    (b) =>
      !filter ||
      b.name.toLowerCase().includes(filter.toLowerCase()) ||
      (b.llcName ?? '').toLowerCase().includes(filter.toLowerCase()) ||
      b.activeZips.some((z) => z.includes(filter)),
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Buyer Intelligence</h1>
          <p className="text-sm text-zinc-500">{buyers.length} buyers · Module 1</p>
        </div>
        <div className="flex gap-3 items-center">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input-field w-48"
            placeholder="Search name, ZIP…"
          />
          <AddBuyerForm onAdded={() => void fetchBuyers()} />
        </div>
      </div>

      {loading ? (
        <div className="text-zinc-500 text-sm">Loading…</div>
      ) : filtered.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
          <p className="text-lg mb-1">No buyers yet</p>
          <p className="text-sm">Add buyers from PropStream, Regrid, or county records.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((buyer) => (
            <BuyerCard key={buyer.id} buyer={buyer} onDelete={() => void deleteBuyer(buyer.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function BuyerCard({ buyer, onDelete }: { buyer: Buyer; onDelete: () => void }) {
  const colorClass = TYPE_COLORS[buyer.type] ?? 'text-zinc-400 bg-zinc-400/10';

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3 hover:border-zinc-600 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold text-zinc-100 truncate">{buyer.llcName ?? buyer.name}</p>
          {buyer.llcName && <p className="text-xs text-zinc-500">{buyer.name}</p>}
        </div>
        <span className={`text-xs font-bold px-2 py-0.5 rounded capitalize shrink-0 ${colorClass}`}>
          {buyer.type}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <p className="text-zinc-500">Buy Box</p>
          <p className="text-zinc-200">
            {fmt(buyer.buyBox.minPrice)} – {fmt(buyer.buyBox.maxPrice)}
          </p>
        </div>
        <div>
          <p className="text-zinc-500">Purchases (24mo)</p>
          <p className="text-zinc-200">{buyer.purchases24mo}</p>
        </div>
      </div>

      {buyer.strategy && (
        <p className="text-xs text-zinc-400 italic">{buyer.strategy}</p>
      )}

      <div className="flex flex-wrap gap-1">
        {buyer.activeZips.slice(0, 6).map((z) => (
          <span key={z} className="text-xs bg-zinc-800 text-zinc-300 px-1.5 py-0.5 rounded">
            {z}
          </span>
        ))}
        {buyer.activeZips.length > 6 && (
          <span className="text-xs text-zinc-500">+{buyer.activeZips.length - 6} more</span>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-zinc-500 pt-1 border-t border-zinc-800">
        <span>{buyer.email ?? buyer.phone ?? 'No contact'}</span>
        <button onClick={onDelete} className="text-red-500 hover:text-red-400 transition-colors">
          Remove
        </button>
      </div>
    </div>
  );
}
