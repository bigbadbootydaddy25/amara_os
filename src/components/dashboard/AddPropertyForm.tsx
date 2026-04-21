'use client';

import { useState } from 'react';

interface Props {
  onAdded: () => void;
}

export default function AddPropertyForm({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    address: '',
    city: '',
    state: '',
    zip: '',
    listingPrice: '',
    description: '',
    listingSource: 'zillow',
    listingUrl: '',
    nearbyListingCount: '',
    parcelAcres: '',
    inBuilderZone: false,
  });

  const field = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const val = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
    setForm((f) => ({ ...f, [k]: val }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    await fetch('/api/properties', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...form,
        listingPrice: form.listingPrice ? Number(form.listingPrice) : undefined,
        nearbyListingCount: form.nearbyListingCount ? Number(form.nearbyListingCount) : undefined,
        parcelAcres: form.parcelAcres ? Number(form.parcelAcres) : undefined,
      }),
    });
    setSaving(false);
    setOpen(false);
    setForm({ address: '', city: '', state: '', zip: '', listingPrice: '', description: '', listingSource: 'zillow', listingUrl: '', nearbyListingCount: '', parcelAcres: '', inBuilderZone: false });
    onAdded();
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-black text-sm font-medium rounded transition-colors"
      >
        + Add Property
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-lg space-y-4"
      >
        <h2 className="font-bold text-zinc-100 text-lg">Add Property</h2>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-zinc-400">Address *</label>
            <input required value={form.address} onChange={field('address')} className="input-field" placeholder="123 Main St" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">City</label>
            <input value={form.city} onChange={field('city')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">State</label>
            <input value={form.state} onChange={field('state')} className="input-field" maxLength={2} placeholder="TX" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">ZIP *</label>
            <input required value={form.zip} onChange={field('zip')} className="input-field" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Listing Price</label>
            <input type="number" value={form.listingPrice} onChange={field('listingPrice')} className="input-field" placeholder="250000" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Source</label>
            <select value={form.listingSource} onChange={field('listingSource')} className="input-field">
              <option value="zillow">Zillow</option>
              <option value="mls">MLS</option>
              <option value="propstream">PropStream</option>
              <option value="manual">Manual</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-400">Nearby Listings</label>
            <input type="number" value={form.nearbyListingCount} onChange={field('nearbyListingCount')} className="input-field" placeholder="0" />
          </div>
          <div>
            <label className="text-xs text-zinc-400">Parcel Acres</label>
            <input type="number" step="0.1" value={form.parcelAcres} onChange={field('parcelAcres')} className="input-field" placeholder="0.25" />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-zinc-400">Listing Description</label>
            <textarea value={form.description} onChange={field('description')} className="input-field h-20 resize-none" placeholder="as-is, investor special, lot 67, estate sale…" />
          </div>
          <div className="col-span-2 flex items-center gap-2">
            <input type="checkbox" id="inBuilderZone" checked={form.inBuilderZone} onChange={field('inBuilderZone')} className="accent-cyan-400" />
            <label htmlFor="inBuilderZone" className="text-sm text-zinc-300">Builder expansion zone</label>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={saving} className="flex-1 py-2 bg-cyan-500 hover:bg-cyan-400 text-black font-medium rounded transition-colors disabled:opacity-50">
            {saving ? 'Saving…' : 'Add Property'}
          </button>
          <button type="button" onClick={() => setOpen(false)} className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-100 rounded transition-colors">
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
