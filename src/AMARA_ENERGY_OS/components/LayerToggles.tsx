'use client';

import { useEnergyStore } from '../stores/energy-store';
import type { LayerKey } from '../types';

const LAYERS: { key: LayerKey; label: string; group?: string }[] = [
  { key: 'wells',          label: 'Wells',           group: 'Data' },
  { key: 'leases',         label: 'Leases',          group: 'Data' },
  { key: 'units',          label: 'Units',           group: 'Data' },
  { key: 'pipelines',      label: 'Pipelines',       group: 'Data' },
  { key: 'producing',      label: 'Producing',       group: 'Status' },
  { key: 'shutIn',         label: 'Shut-In',         group: 'Status' },
  { key: 'duc',            label: 'DUC',             group: 'Status' },
  { key: 'titleRisk',      label: 'Title Risk',      group: 'Risk' },
  { key: 'curativeNeeded', label: 'Curative Needed', group: 'Risk' },
  { key: 'nptAlerts',      label: 'NPT Alerts',      group: 'Risk' },
];

const GROUP_COLOR: Record<string, string> = {
  Data:   '#00aaff',
  Status: '#00cc88',
  Risk:   '#ff8c00',
};

export function LayerToggles() {
  const layers      = useEnergyStore((s) => s.layers);
  const toggleLayer = useEnergyStore((s) => s.toggleLayer);

  const groups = ['Data', 'Status', 'Risk'];

  return (
    <div className="pointer-events-auto absolute left-4 top-12 z-30 flex flex-col gap-2 rounded border border-[#00aaff]/15 bg-[#010c1a]/85 p-3 backdrop-blur-xl"
      style={{ minWidth: 148 }}>
      <p className="font-mono text-[7px] uppercase tracking-[0.4em] text-white/25">
        Map Layers
      </p>
      {groups.map((grp) => (
        <div key={grp}>
          <p className="mb-1 font-mono text-[7px] uppercase tracking-[0.3em]"
            style={{ color: GROUP_COLOR[grp] + '80' }}>
            {grp}
          </p>
          <div className="flex flex-col gap-1">
            {LAYERS.filter((l) => l.group === grp).map(({ key, label }) => {
              const active = layers[key];
              const color  = GROUP_COLOR[grp];
              return (
                <button
                  key={key}
                  onClick={() => toggleLayer(key)}
                  className="flex items-center gap-2 rounded px-2 py-1 text-left transition-all duration-150"
                  style={{
                    background: active ? `${color}14` : 'transparent',
                    border:     `1px solid ${active ? color + '55' : '#ffffff10'}`,
                  }}
                >
                  {/* indicator dot */}
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full transition-all"
                    style={{
                      background: active ? color : '#ffffff22',
                      boxShadow:  active ? `0 0 5px ${color}` : 'none',
                    }} />
                  <span className="font-mono text-[9px] font-medium tracking-wide"
                    style={{ color: active ? '#ffffff' : '#ffffff40' }}>
                    {label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
