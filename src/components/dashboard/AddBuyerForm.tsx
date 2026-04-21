'use client';

import { useState } from 'react';
import type { BuyerType } from '@/types/real-estate';

interface Props {
  onAdded: () => void;
}

export default function AddBuyerForm({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: '',
    llcName: '',
    email: '',
    phone: '',
    type: 'builder' as BuyerType,
    activeZips: '',
    minPrice: '',
    maxPrice: '',
    strategy: '',
    purchases24mo: '',
    purchases36mo: '',
  });

  const field = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    await fetch('/api/buyers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.name,
        llcName: form.llcName || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        type: form.type,
        activeZips: form.activeZips.split(',').map((z) => z.trim()).filter(Boolean),
        buyBox: {
          minPrice: Number(form.minPrice) || 0,
          maxPrice: Number(form.maxPrice) || 9_999_999,
          propertyTypes: ['SFR', 'Land'],
          strategy: form.strategy,
        },
        strategy: form.strategy,
        purchases24mo: Number(form.purchases24mo) || 0,
        purchases36mo: Number(form.purchases36mo) || 0,
        confidenceScore: 5,
      }),
    });
    setSaving(false);
    setOpen(false);
    onAdded();
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-black text-sm font-medium rounded transition-colors"
      >
        + Add Buyer
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-lg space-y-4"
      >
        <h2 className="font-bold text-zinc-100 text-lg">Add Buyer</h2>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-zinc-400">Name *</label>
            <input required value={form.name} onChange={field('name')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">LLC Name</label>
            <input value={form.llcName} onChange={field('llcName')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Email</label>
            <input type="email" value={form.email} onChange={field('email')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Phone</label>
            <input value={form.phone} onChange={field('phone')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Buyer Type</label>
            <select value={form.type} onChange={field('type')} className="input-field">
              <option value="builder">Builder</option>
              <option value="flipper">Flipper</option>
              <option value="landlord">Landlord</option>
              <option value="developer">Developer</option>
              <option value="wholesaler">Wholesaler</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-400">Strategy</label>
            <input value={form.strategy} onChange={field('strategy')} className="input-field" placeholder="New construction, SFR flip…" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Min Price ($)</label>
            <input type="number" value={form.minPrice} onChange={field('minPrice')} className="input-field" placeholder="50000" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Max Price ($)</label>
            <input type="number" value={form.maxPrice} onChange={field('maxPrice')} className="input-field" placeholder="500000" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Purchases (24mo)</label>
            <input type="number" value={form.purchases24mo} onChange={field('purchases24mo')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Purchases (36mo)</label>
            <input type="number" value={form.purchases36mo} onChange={field('purchases36mo')} className="input-field" />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-zinc-400">Active ZIPs (comma-separated)</label>
            <input value={form.activeZips} onChange={field('activeZips')} className="input-field" placeholder="78701, 78702, 78703" />
          </div>
        </div>
        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={saving} className="flex-1 py-2 bg-cyan-500 hover:bg-cyan-400 text-black font-medium rounded transition-colors disabled:opacity-50">
            {saving ? 'Saving…' : 'Add Buyer'}
          </button>
          <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-100 rounded transition-colors">
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
