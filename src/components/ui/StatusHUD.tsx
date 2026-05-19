'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useAgentStore } from '@/stores/agent-store';
import { AGENT_DEFINITIONS } from '@/types/agents';
import type { AgentStatus } from '@/types/agents';

const DOT_COLOR: Record<AgentStatus, string> = {
  idle: '#1a3040',
  searching: '#7c3aed',
  processing: '#00aaff',
  verified: '#00ff88',
  nuclear: '#ff4400',
};

export function StatusHUD() {
  const { agents, amaraStatus, totalVerified, nuclearCount, findings } = useAgentStore();

  const activeCount = Object.values(agents).filter(
    (a) => a.status !== 'idle',
  ).length;

  const latestFinding = findings[0];

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 pointer-events-none">
      {/* Latest finding ticker */}
      <AnimatePresence mode="wait">
        {latestFinding && (
          <motion.div
            key={latestFinding.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.4 }}
            className="flex justify-center mb-3"
          >
            <div
              className="text-[10px] font-mono px-4 py-1.5 rounded-full tracking-widest"
              style={{
                background: 'rgba(0,0,0,0.7)',
                border: `1px solid ${latestFinding.value === 'nuclear' ? '#ff440044' : '#00aaff22'}`,
                color: latestFinding.value === 'nuclear' ? '#ff6600' : '#00aaff88',
              }}
            >
              {latestFinding.value === 'nuclear' ? '⚡ NUCLEAR: ' : '◈ '}
              {latestFinding.summary}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bottom HUD bar */}
      <div
        className="mx-4 mb-4 rounded-2xl px-6 py-3 flex items-center justify-between"
        style={{
          background: 'rgba(1, 8, 18, 0.85)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(0, 212, 255, 0.12)',
          boxShadow: '0 0 40px rgba(0, 100, 150, 0.15)',
        }}
      >
        {/* AMARA status */}
        <div className="flex items-center gap-3">
          <div
            className="w-2 h-2 rounded-full"
            style={{
              background: amaraStatus === 'nuclear' ? '#ff4400' : '#00d4ff',
              boxShadow: `0 0 8px ${amaraStatus === 'nuclear' ? '#ff4400' : '#00d4ff'}`,
              animation: 'pulse 1.5s infinite',
            }}
          />
          <div>
            <div
              className="text-[10px] font-bold tracking-widest uppercase"
              style={{ color: amaraStatus === 'nuclear' ? '#ff6600' : '#00d4ff' }}
            >
              AMARA
            </div>
            <div className="text-[8px] text-slate-600 tracking-wider">
              {amaraStatus === 'nuclear' ? 'NUCLEAR LOCK' : 'ENERGY OS · ONLINE'}
            </div>
          </div>
        </div>

        {/* Agent status dots */}
        <div className="flex items-center gap-2">
          {AGENT_DEFINITIONS.map((def) => {
            const status = agents[def.id].status;
            return (
              <div
                key={def.id}
                className="relative"
                title={`${def.label}: ${status}`}
              >
                <div
                  className="w-1.5 h-1.5 rounded-full transition-all duration-500"
                  style={{
                    background: DOT_COLOR[status],
                    boxShadow: status !== 'idle' ? `0 0 6px ${DOT_COLOR[status]}` : 'none',
                  }}
                />
              </div>
            );
          })}
          <div className="text-[9px] text-slate-600 ml-2 font-mono">
            {activeCount}/{AGENT_DEFINITIONS.length} active
          </div>
        </div>

        {/* Right stats */}
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="text-lg font-bold text-emerald-400 leading-none">
              {totalVerified}
            </div>
            <div className="text-[8px] text-slate-600 uppercase tracking-widest">Verified</div>
          </div>
          <div className="text-center">
            <div
              className="text-lg font-bold leading-none"
              style={{ color: nuclearCount > 0 ? '#ff4400' : '#334455' }}
            >
              {nuclearCount}
            </div>
            <div className="text-[8px] text-slate-600 uppercase tracking-widest">Nuclear</div>
          </div>
        </div>
      </div>
    </div>
  );
}
