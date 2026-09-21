import type { SepticSuitability } from '@/lib/land/soil';

const STYLES: Record<SepticSuitability, { label: string; className: string }> = {
  'likely-suitable': { label: 'LIKELY SUITABLE', className: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  caution: { label: 'CAUTION', className: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
  poor: { label: 'POOR', className: 'bg-red-500/20 text-red-300 border-red-500/40' },
  unknown: { label: 'UNKNOWN', className: 'bg-slate-500/20 text-slate-300 border-slate-500/40' },
};

export function SoilBadge({ suitability }: { suitability: SepticSuitability }) {
  const style = STYLES[suitability];
  return (
    <span
      data-testid="soil-badge"
      data-suitability={suitability}
      className={`inline-block rounded border px-2 py-0.5 text-xs font-semibold tracking-wide ${style.className}`}
    >
      {style.label}
    </span>
  );
}
