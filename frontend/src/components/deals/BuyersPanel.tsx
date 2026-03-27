import { useState, useEffect } from "react";
import type { Buyer } from "../../types/deals";
import { api } from "../../api/client";
import styles from "./BuyersPanel.module.css";

export function BuyersPanel() {
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Buyer | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listBuyers();
      setBuyers(res.data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this buyer?")) return;
    await api.deleteBuyer(id);
    setBuyers((b) => b.filter((x) => x.id !== id));
  }

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <span className={styles.title}>Buyers ({buyers.filter((b) => b.isActive).length} active)</span>
        <button className={styles.addBtn} onClick={() => { setEditing(null); setShowForm(true); }}>
          + Add Buyer
        </button>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {loading && <div className={styles.loading}>Loading buyers…</div>}

      <div className={styles.list}>
        {buyers.map((b) => (
          <div key={b.id} className={`${styles.card} ${!b.isActive ? styles.inactive : ""}`}>
            <div className={styles.cardTop}>
              <div>
                <div className={styles.buyerName}>{b.name}</div>
                <div className={styles.buyerContact}>
                  {[b.company, b.email, b.phone].filter(Boolean).join(" · ") || "No contact info"}
                </div>
              </div>
              <div className={styles.cardActions}>
                <button onClick={() => { setEditing(b); setShowForm(true); }}>Edit</button>
                <button onClick={() => handleDelete(b.id)} className={styles.deleteBtn}>✕</button>
              </div>
            </div>
            <div className={styles.buyBox}>
              {b.propertyTypes?.length && <Chip>{b.propertyTypes.join("/")}</Chip>}
              {(b.priceMin || b.priceMax) && (
                <Chip>${numK(b.priceMin)}K – ${numK(b.priceMax)}K</Chip>
              )}
              {(b.bedsMin || b.bedsMax) && (
                <Chip>{b.bedsMin ?? "?"}-{b.bedsMax ?? "?"}bd</Chip>
              )}
              {b.minRoiPct && <Chip>ROI ≥ {Number(b.minRoiPct).toFixed(0)}%</Chip>}
              {b.zipCodes?.length && <Chip>{b.zipCodes.slice(0, 3).join(", ")}{b.zipCodes.length > 3 ? ` +${b.zipCodes.length - 3}` : ""}</Chip>}
              {b.states?.length && <Chip>{b.states.join(", ")}</Chip>}
            </div>
          </div>
        ))}
        {!loading && !buyers.length && (
          <div className={styles.empty}>No buyers yet. Add your first buyer to start matching.</div>
        )}
      </div>

      {showForm && (
        <BuyerForm
          initial={editing}
          onSave={async (data) => {
            if (editing) {
              const res = await api.updateBuyer(editing.id, data);
              setBuyers((b) => b.map((x) => x.id === editing.id ? res.data : x));
            } else {
              const res = await api.createBuyer(data);
              setBuyers((b) => [...b, res.data]);
            }
            setShowForm(false);
          }}
          onClose={() => setShowForm(false)}
        />
      )}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return <span className={styles.chip}>{children}</span>;
}

function numK(v: string | null | undefined) {
  if (!v) return "?";
  return Math.round(Number(v) / 1000);
}

// ── Buyer form ────────────────────────────────────────────────────────────────
function BuyerForm({
  initial,
  onSave,
  onClose,
}: {
  initial: Buyer | null;
  onSave: (data: Partial<Buyer>) => Promise<void>;
  onClose: () => void;
}) {
  const [form, setForm] = useState({
    name:         initial?.name          ?? "",
    email:        initial?.email         ?? "",
    phone:        initial?.phone         ?? "",
    company:      initial?.company       ?? "",
    propertyTypes: (initial?.propertyTypes ?? []).join(", "),
    bedsMin:      initial?.bedsMin       ?? "",
    bedsMax:      initial?.bedsMax       ?? "",
    bathsMin:     initial?.bathsMin      ?? "",
    bathsMax:     initial?.bathsMax      ?? "",
    priceMin:     initial?.priceMin      ?? "",
    priceMax:     initial?.priceMax      ?? "",
    arvMin:       initial?.arvMin        ?? "",
    arvMax:       initial?.arvMax        ?? "",
    maxRehab:     initial?.maxRehab      ?? "",
    minRoiPct:    initial?.minRoiPct     ?? "",
    zipCodes:     (initial?.zipCodes ?? []).join(", "),
    states:       (initial?.states  ?? []).join(", "),
    notes:        initial?.notes         ?? "",
    isActive:     initial?.isActive      ?? true,
  });
  const [saving, setSaving] = useState(false);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const payload = {
      name:    form.name,
      email:   form.email   || undefined,
      phone:   form.phone   || undefined,
      company: form.company || undefined,
      propertyTypes: form.propertyTypes ? form.propertyTypes.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      bedsMin:  form.bedsMin  ? parseInt(form.bedsMin  as string, 10) : undefined,
      bedsMax:  form.bedsMax  ? parseInt(form.bedsMax  as string, 10) : undefined,
      bathsMin: form.bathsMin ? parseFloat(form.bathsMin as string) : undefined,
      bathsMax: form.bathsMax ? parseFloat(form.bathsMax as string) : undefined,
      priceMin: form.priceMin ? Number(form.priceMin) : undefined,
      priceMax: form.priceMax ? Number(form.priceMax) : undefined,
      arvMin:   form.arvMin   ? Number(form.arvMin) : undefined,
      arvMax:   form.arvMax   ? Number(form.arvMax) : undefined,
      maxRehab: form.maxRehab ? Number(form.maxRehab) : undefined,
      minRoiPct: form.minRoiPct ? Number(form.minRoiPct) : undefined,
      zipCodes: form.zipCodes ? form.zipCodes.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      states:   form.states   ? form.states.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      notes:    form.notes || undefined,
      isActive: form.isActive,
    };
    try {
      await onSave(payload as Partial<Buyer>);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <form className={styles.form} onSubmit={handleSubmit} onClick={(e) => e.stopPropagation()}>
        <div className={styles.formHeader}>
          <span>{initial ? "Edit Buyer" : "New Buyer"}</span>
          <button type="button" className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.formGrid}>
          <F label="Name*"><input required value={form.name} onChange={set("name")} placeholder="John Smith" /></F>
          <F label="Email"><input type="email" value={form.email as string} onChange={set("email")} placeholder="john@email.com" /></F>
          <F label="Phone"><input value={form.phone as string} onChange={set("phone")} placeholder="(702) 555-0100" /></F>
          <F label="Company"><input value={form.company as string} onChange={set("company")} placeholder="Smith Acquisitions LLC" /></F>

          <div className={styles.divider}>Buy Box Criteria</div>

          <F label="Property Types (comma-sep)"><input value={form.propertyTypes as string} onChange={set("propertyTypes")} placeholder="SFR, MF, Land" /></F>
          <F label="Price Min ($)"><input type="number" value={form.priceMin as string} onChange={set("priceMin")} placeholder="150000" /></F>
          <F label="Price Max ($)"><input type="number" value={form.priceMax as string} onChange={set("priceMax")} placeholder="400000" /></F>
          <F label="ARV Min ($)"><input type="number" value={form.arvMin as string} onChange={set("arvMin")} placeholder="200000" /></F>
          <F label="ARV Max ($)"><input type="number" value={form.arvMax as string} onChange={set("arvMax")} placeholder="600000" /></F>
          <F label="Beds Min"><input type="number" value={form.bedsMin as string} onChange={set("bedsMin")} placeholder="2" /></F>
          <F label="Beds Max"><input type="number" value={form.bedsMax as string} onChange={set("bedsMax")} placeholder="5" /></F>
          <F label="Baths Min"><input type="number" step="0.5" value={form.bathsMin as string} onChange={set("bathsMin")} placeholder="1" /></F>
          <F label="Baths Max"><input type="number" step="0.5" value={form.bathsMax as string} onChange={set("bathsMax")} placeholder="3" /></F>
          <F label="Max Rehab ($)"><input type="number" value={form.maxRehab as string} onChange={set("maxRehab")} placeholder="60000" /></F>
          <F label="Min ROI %"><input type="number" step="0.1" value={form.minRoiPct as string} onChange={set("minRoiPct")} placeholder="15" /></F>
          <F label="Target ZIPs (comma-sep)"><input value={form.zipCodes as string} onChange={set("zipCodes")} placeholder="89014, 89129, 89108" /></F>
          <F label="Target States (comma-sep)"><input value={form.states as string} onChange={set("states")} placeholder="NV, AZ, TX" /></F>
          <F label="Notes" full><textarea value={form.notes as string} onChange={set("notes")} rows={2} placeholder="Prefers distressed, off-market…" /></F>
        </div>

        <div className={styles.formFooter}>
          <label className={styles.activeCheck}>
            <input type="checkbox" checked={form.isActive as boolean}
              onChange={(e) => setForm((f) => ({ ...f, isActive: e.target.checked }))} />
            Active buyer
          </label>
          <div className={styles.formBtns}>
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" className={styles.saveBtn} disabled={saving}>
              {saving ? "Saving…" : "Save Buyer"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

function F({ label, children, full }: { label: string; children: React.ReactNode; full?: boolean }) {
  return (
    <label className={`${styles.field} ${full ? styles.fieldFull : ""}`}>
      <span className={styles.fieldLabel}>{label}</span>
      {children}
    </label>
  );
}
