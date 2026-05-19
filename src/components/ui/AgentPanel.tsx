'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { AGENT_DEFINITIONS } from '@/types/agents';
import { useAgentStore } from '@/stores/agent-store';

const STATUS_LABEL: Record<string, string> = {
  idle: 'STANDBY',
  searching: 'SCANNING',
  processing: 'PROCESSING',
  verified: 'TARGET VERIFIED',
  nuclear: 'NUCLEAR HIT',
};

const STATUS_COLOR: Record<string, string> = {
  idle: '#334455',
  searching: '#7c3aed',
  processing: '#00aaff',
  verified: '#00ff88',
  nuclear: '#ff4400',
};

export function AgentPanel() {
  const { selectedAgentId, agents, findings, clearSelected } = useAgentStore();

  const def = AGENT_DEFINITIONS.find((d) => d.id === selectedAgentId);
  const state = selectedAgentId ? agents[selectedAgentId] : null;

  const agentFindings = findings
    .filter((f) => f.agentId === selectedAgentId)
    .slice(0, 6);

  return (
    <AnimatePresence>
      {def && state && (
        <motion.div
          key={def.id}
          initial={{ opacity: 0, x: 40, scale: 0.95 }}
          animate={{ opacity: 1, x: 0, scale: 1 }}
          exit={{ opacity: 0, x: 40, scale: 0.95 }}
          transition={{ duration: 0.28, ease: 'easeOut' }}
          className="fixed right-6 top-1/2 -translate-y-1/2 w-80 z-40 pointer-events-auto"
        >
          <div
            className="rounded-xl border overflow-hidden backdrop-blur-md"
            style={{
              background: 'rgba(1, 8, 18, 0.88)',
              borderColor: def.color + '44',
              boxShadow: `0 0 40px ${def.color}22, 0 0 80px ${def.color}11`,
            }}
          >
            {/* Header */}
            <div
              className="px-5 py-4 flex items-start justify-between"
              style={{ borderBottom: `1px solid ${def.color}22` }}
            >
              <div>
                <div
                  className="text-xs font-bold tracking-widest uppercase mb-1"
                  style={{ color: def.color, textShadow: `0 0 10px ${def.color}` }}
                >
                  {def.label}
                </div>
                <div className="text-[10px] text-slate-500 tracking-wider">{def.subLabel}</div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <button
                  onClick={clearSelected}
                  className="text-slate-600 hover:text-slate-300 transition-colors text-xs"
                >
                  ✕
                </button>
                <div
                  className="text-[10px] font-bold tracking-widest px-2 py-1 rounded"
                  style={{
                    color: STATUS_COLOR[state.status],
                    background: STATUS_COLOR[state.status] + '22',
                    border: `1px solid ${STATUS_COLOR[state.status]}44`,
                  }}
                >
                  {STATUS_LABEL[state.status]}
                </div>
              </div>
            </div>

            {/* Body */}
            <div className="px-5 py-4 space-y-4">
              {/* Current task */}
              {state.currentTask && (
                <div>
                  <div className="text-[9px] text-slate-600 uppercase tracking-widest mb-1">
                    Active Task
                  </div>
                  <div className="text-[11px] text-slate-300 font-mono leading-relaxed">
                    {state.currentTask}
                  </div>
                </div>
              )}

              {/* Description */}
              <div>
                <div className="text-[9px] text-slate-600 uppercase tracking-widest mb-1">
                  Mission
                </div>
                <div className="text-[11px] text-slate-400 leading-relaxed">
                  {def.description}
                </div>
              </div>

              {/* OSINT sources */}
              <div>
                <div className="text-[9px] text-slate-600 uppercase tracking-widest mb-2">
                  OSINT Sources
                </div>
                <div className="flex flex-wrap gap-1">
                  {def.dataSources.map((src) => (
                    <span
                      key={src}
                      className="text-[9px] px-2 py-0.5 rounded font-mono"
                      style={{
                        background: def.color + '15',
                        border: `1px solid ${def.color}33`,
                        color: def.color,
                      }}
                    >
                      {src}
                    </span>
                  ))}
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div
                  className="rounded-lg p-3 text-center"
                  style={{ background: def.color + '0f', border: `1px solid ${def.color}22` }}
                >
                  <div
                    className="text-2xl font-bold"
                    style={{ color: def.color }}
                  >
                    {state.findingsCount}
                  </div>
                  <div className="text-[9px] text-slate-500 uppercase tracking-wider mt-1">
                    Signals
                  </div>
                </div>
                <div
                  className="rounded-lg p-3 text-center"
                  style={{ background: '#00ff8810', border: '1px solid #00ff8822' }}
                >
                  <div className="text-2xl font-bold text-emerald-400">
                    {state.verifiedTargets.length}
                  </div>
                  <div className="text-[9px] text-slate-500 uppercase tracking-wider mt-1">
                    Verified
                  </div>
                </div>
              </div>

              {/* Recent activity log */}
              {agentFindings.length > 0 && (
                <div>
                  <div className="text-[9px] text-slate-600 uppercase tracking-widest mb-2">
                    Activity Log
                  </div>
                  <div className="space-y-1.5 max-h-32 overflow-y-auto">
                    {agentFindings.map((f) => (
                      <motion.div
                        key={f.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="text-[9px] font-mono flex items-center gap-2 text-slate-500"
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{
                            background:
                              f.value === 'nuclear'
                                ? '#ff4400'
                                : f.value === 'high'
                                  ? '#00ff88'
                                  : def.color,
                          }}
                        />
                        <span className="truncate">{f.summary}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
