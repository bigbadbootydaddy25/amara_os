'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useEnergyStore } from '../stores/energy-store';
import type { AgentStatus } from '../types';

const STATUS_COLOR: Record<AgentStatus, string> = {
  idle:      '#ffffff30',
  scanning:  '#00ccff',
  analyzing: '#ffd000',
  flagged:   '#ff8c00',
  critical:  '#ff3300',
};

const STATUS_LABEL: Record<AgentStatus, string> = {
  idle:      'Idle',
  scanning:  'Scanning',
  analyzing: 'Analyzing',
  flagged:   'Flagged',
  critical:  'Critical',
};

function timeSince(ts: number) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60)  return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export function AgentActivityPanel() {
  const agents    = useEnergyStore((s) => s.agents);
  const open      = useEnergyStore((s) => s.agentPanelOpen);
  const setOpen   = useEnergyStore((s) => s.setAgentPanelOpen);

  return (
    <div className="pointer-events-auto absolute bottom-14 right-4 z-30" style={{ width: 310 }}>
      {/* toggle tab */}
      <button
        onClick={() => setOpen(!open)}
        className="mb-1 flex w-full items-center justify-between rounded border border-[#00aaff]/18 bg-[#010c1a]/85 px-3 py-1.5 backdrop-blur-xl transition-colors hover:border-[#00aaff]/35"
      >
        <span className="font-mono text-[8px] uppercase tracking-[0.4em] text-[#00aaff]/60">
          Agent Activity
        </span>
        <span className="font-mono text-[10px] text-white/30">{open ? '▾' : '▸'}</span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden rounded border border-[#00aaff]/12 bg-[#010c1a]/90 backdrop-blur-2xl"
          >
            <div className="divide-y divide-[#00aaff]/06">
              {agents.map((agent) => {
                const col = STATUS_COLOR[agent.status];
                return (
                  <div key={agent.id} className="px-3 py-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {/* status dot */}
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ background: col, boxShadow: agent.status !== 'idle' ? `0 0 5px ${col}` : 'none' }}
                        />
                        <span className="font-mono text-[10px] font-semibold tracking-wide text-white/85">
                          {agent.name}
                        </span>
                      </div>
                      <span
                        className="font-mono text-[7px] uppercase tracking-widest"
                        style={{ color: col }}
                      >
                        {STATUS_LABEL[agent.status]}
                      </span>
                    </div>
                    {/* latest finding */}
                    <AnimatePresence mode="wait">
                      <motion.p
                        key={agent.findingTs}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.3 }}
                        className="mt-1 font-mono text-[9px] leading-snug text-white/38 line-clamp-2"
                      >
                        {agent.finding}
                      </motion.p>
                    </AnimatePresence>
                    <p className="mt-0.5 font-mono text-[7px] text-white/18">
                      {timeSince(agent.findingTs)}
                    </p>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
