'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useEnergyStore } from '../stores/energy-store';
import type { WellPad, NptRisk, WellStatus, ProductionStatus, LeaseStatus } from '../types';

// ── color maps ────────────────────────────────────────────────────────────────

const NPT_COLOR: Record<NptRisk, string> = {
  Low:      'text-emerald-400 border-emerald-400/30 bg-emerald-400/10',
  Medium:   'text-yellow-400  border-yellow-400/30  bg-yellow-400/10',
  High:     'text-orange-400  border-orange-400/30  bg-orange-400/10',
  Critical: 'text-red-400     border-red-400/30     bg-red-400/10',
};

const STATUS_COLOR: Record<WellStatus, string> = {
  'Active':  'text-emerald-400',
  'Shut-In': 'text-yellow-400',
  'DUC':     'text-cyan-400',
  'P&A':     'text-white/40',
  'Permit':  'text-purple-400',
};

const PROD_COLOR: Record<ProductionStatus, string> = {
  'Producing':          'text-emerald-400',
  'Shut-In':            'text-yellow-400',
  'Not Yet Producing':  'text-white/40',
  'DUC':                'text-cyan-400',
};

const LEASE_COLOR: Record<LeaseStatus, string> = {
  'HBP':            'text-emerald-400',
  'Active':         'text-cyan-400',
  'Expiring <60d':  'text-yellow-400',
  'Expiring <30d':  'text-orange-400',
  'Expired':        'text-red-400',
};

// ── sub-components ────────────────────────────────────────────────────────────

function Field({ label, value, valueClass = 'text-white/80' }: { label: string; value: string; valueClass?: string }) {
  return (
    <div>
      <p className="font-mono text-[8px] uppercase tracking-[0.3em] text-white/30">{label}</p>
      <p className={`mt-0.5 font-mono text-[11px] font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}

function Badge({ text, className }: { text: string; className: string }) {
  return (
    <span className={`inline-block rounded border px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest ${className}`}>
      {text}
    </span>
  );
}

function FlagList({ flags, color }: { flags: string[]; color: string }) {
  if (flags.length === 0) {
    return <p className="font-mono text-[10px] text-white/25 italic">None</p>;
  }
  return (
    <ul className="space-y-1">
      {flags.map((f) => (
        <li key={f} className={`flex items-start gap-1.5 font-mono text-[10px] leading-snug ${color}`}>
          <span className="mt-0.5 shrink-0">▸</span>
          <span>{f}</span>
        </li>
      ))}
    </ul>
  );
}

// ── drawer ────────────────────────────────────────────────────────────────────

export function WellDrawer() {
  const selectedId  = useEnergyStore((s) => s.selectedWellId);
  const wells       = useEnergyStore((s) => s.wells);
  const selectWell  = useEnergyStore((s) => s.selectWell);

  const well = wells.find((w) => w.id === selectedId) ?? null;

  function fmt(iso: string) {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: '2-digit', minute: '2-digit', timeZoneName: 'short',
    });
  }

  return (
    <AnimatePresence>
      {well && (
        <motion.aside
          key={well.id}
          initial={{ x: 380, opacity: 0 }}
          animate={{ x: 0,   opacity: 1 }}
          exit={{ x: 380,    opacity: 0 }}
          transition={{ type: 'spring', stiffness: 340, damping: 34 }}
          className="pointer-events-auto fixed right-0 top-0 z-40 flex h-full w-[340px] flex-col border-l border-[#00aaff]/15 bg-[#010c1a]/90 backdrop-blur-2xl"
          style={{ boxShadow: '-1px 0 60px rgba(0,170,255,0.08)' }}
        >
          {/* ── header ────────────────────────────────────────────────────── */}
          <div className="border-b border-[#00aaff]/12 px-5 py-4"
            style={{ background: 'linear-gradient(90deg, rgba(0,60,120,0.25) 0%, transparent 100%)' }}>
            <div className="flex items-start justify-between">
              <div>
                <p className="font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/50">
                  Well Detail
                </p>
                <h2 className="mt-0.5 font-mono text-base font-bold tracking-wide text-white">
                  {well.name}
                </h2>
                <p className="mt-0.5 font-mono text-[10px] tracking-widest text-[#00aaff]/70">
                  {well.apiNumber}
                </p>
              </div>
              <button
                onClick={() => selectWell(null)}
                className="mt-0.5 rounded p-1.5 font-mono text-sm text-white/25 transition-colors hover:text-white/60"
                aria-label="Close drawer"
              >
                ✕
              </button>
            </div>

            {/* status badges */}
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge text={well.wellStatus}       className={STATUS_COLOR[well.wellStatus] + ' border-current/30 bg-current/5'} />
              <Badge text={well.productionStatus} className={PROD_COLOR[well.productionStatus] + ' border-current/30 bg-current/5'} />
              <Badge text={`NPT: ${well.nptRisk}`} className={NPT_COLOR[well.nptRisk]} />
            </div>
          </div>

          {/* ── scrollable body ────────────────────────────────────────────── */}
          <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">

            {/* location & operator */}
            <section>
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/40">
                Location & Operator
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Operator" value={well.operator} />
                <Field label="County"   value={well.county} />
                <Field label="Basin"    value={well.basin} />
                <Field label="State"    value="Texas" />
              </div>
            </section>

            <div className="h-px bg-[#00aaff]/08" />

            {/* lease / HBP */}
            <section>
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/40">
                Lease / HBP Status
              </p>
              <Badge text={well.leaseStatus} className={LEASE_COLOR[well.leaseStatus] + ' border-current/30 bg-current/5'} />
            </section>

            <div className="h-px bg-[#00aaff]/08" />

            {/* title flags */}
            <section>
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/40">
                Title Flags
              </p>
              <FlagList flags={well.titleFlags} color="text-orange-300/85" />
            </section>

            <div className="h-px bg-[#00aaff]/08" />

            {/* curative flags */}
            <section>
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/40">
                Curative Actions
              </p>
              <FlagList flags={well.curativeFlags} color="text-yellow-300/85" />
            </section>

            <div className="h-px bg-[#00aaff]/08" />

            {/* well status detail */}
            <section>
              <p className="mb-2 font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/40">
                Operational Detail
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Well Status"       value={well.wellStatus}       valueClass={STATUS_COLOR[well.wellStatus]} />
                <Field label="Production Status" value={well.productionStatus} valueClass={PROD_COLOR[well.productionStatus]} />
                <Field label="NPT Risk"          value={well.nptRisk}          valueClass={NPT_COLOR[well.nptRisk].split(' ')[0]} />
                <Field label="API Number"        value={well.apiNumber} />
              </div>
            </section>
          </div>

          {/* ── footer ────────────────────────────────────────────────────── */}
          <div className="border-t border-[#00aaff]/10 px-5 py-3">
            <p className="font-mono text-[8px] uppercase tracking-[0.3em] text-white/20">
              Last Updated
            </p>
            <p className="mt-0.5 font-mono text-[9px] text-white/40">
              {fmt(well.lastUpdated)}
            </p>
            <p className="mt-1 font-mono text-[8px] uppercase tracking-widest text-[#ff8c00]/50">
              ⚠ All data is demo / synthetic
            </p>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
