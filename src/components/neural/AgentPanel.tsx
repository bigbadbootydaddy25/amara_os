'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useNeuralStore, AGENT_CONFIG } from '@/stores/neural-store';

const STATE_LABEL: Record<string, string> = {
  idle: 'STANDBY',
  searching: 'SEARCHING',
  processing: 'PROCESSING',
  verified: 'VERIFIED',
  nuclear: 'NUCLEAR',
};

const STATE_COLOR: Record<string, string> = {
  idle: 'text-white/40',
  searching: 'text-cyan-400',
  processing: 'text-yellow-400',
  verified: 'text-emerald-400',
  nuclear: 'text-orange-500',
};

export function AgentPanel() {
  const selectedId = useNeuralStore((s) => s.selectedAgentId);
  const agents = useNeuralStore((s) => s.agents);
  const selectAgent = useNeuralStore((s) => s.selectAgent);

  const agent = agents.find((a) => a.id === selectedId) ?? null;
  const cfg = AGENT_CONFIG.find((c) => c.id === selectedId) ?? null;

  return (
    <AnimatePresence>
      {agent && cfg && (
        <motion.div
          key={agent.id}
          initial={{ x: 340, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 340, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 320, damping: 32 }}
          className="pointer-events-auto fixed right-0 top-0 z-30 flex h-full w-80 flex-col border-l border-white/8 bg-black/72 backdrop-blur-xl"
          style={{ boxShadow: `-1px 0 40px ${cfg.color}18` }}
        >
          {/* header */}
          <div className="flex items-start justify-between border-b border-white/8 px-5 py-4">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-white/40">
                Agent
              </p>
              <h2 className="mt-0.5 font-mono text-xl font-bold tracking-widest" style={{ color: cfg.color }}>
                {cfg.name}
              </h2>
              <p className={`mt-1 font-mono text-[11px] font-semibold tracking-widest ${STATE_COLOR[agent.state]}`}>
                {STATE_LABEL[agent.state]}
              </p>
            </div>
            <button
              onClick={() => selectAgent(null)}
              className="mt-1 rounded p-1 font-mono text-sm text-white/30 transition-colors hover:text-white/70"
              aria-label="Close"
            >
              ✕
            </button>
          </div>

          {/* mission */}
          <div className="border-b border-white/8 px-5 py-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-white/35">Mission</p>
            <p className="mt-1 text-[12px] leading-relaxed text-white/70">{cfg.mission}</p>
          </div>

          {/* sources */}
          <div className="border-b border-white/8 px-5 py-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-white/35">OSINT Sources</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {cfg.sources.map((src) => (
                <span
                  key={src}
                  className="rounded border border-white/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-white/50"
                >
                  {src}
                </span>
              ))}
            </div>
          </div>

          {/* stats */}
          <div className="flex border-b border-white/8">
            <div className="flex-1 border-r border-white/8 px-5 py-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-white/35">Signals</p>
              <p className="mt-1 font-mono text-2xl font-bold text-white/80">{agent.signalCount}</p>
            </div>
            <div className="flex-1 px-5 py-3">
              <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-white/35">Verified</p>
              <p className="mt-1 font-mono text-2xl font-bold text-emerald-400">{agent.verifiedCount}</p>
            </div>
          </div>

          {/* activity log */}
          <div className="flex min-h-0 flex-1 flex-col px-5 py-3">
            <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.3em] text-white/35">
              Activity Log
            </p>
            <div className="flex-1 space-y-2 overflow-y-auto pr-1 scrollbar-thin">
              {agent.activityLog.length === 0 ? (
                <p className="font-mono text-[10px] text-white/25 italic">No activity yet</p>
              ) : (
                agent.activityLog.map((entry) => (
                  <div key={entry.timestamp} className="border-l-2 border-white/10 pl-3">
                    <p className="font-mono text-[9px] text-white/30">
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </p>
                    <p className="mt-0.5 font-mono text-[10px] leading-snug text-white/65">
                      {entry.message}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
