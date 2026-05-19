'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useNeuralStore, AGENT_CONFIG } from '@/stores/neural-store';

const DOT_COLOR: Record<string, string> = {
  idle: 'bg-white/20',
  searching: 'bg-cyan-400',
  processing: 'bg-yellow-400',
  verified: 'bg-emerald-400',
  nuclear: 'bg-orange-500',
};

export function StatusHUD() {
  const agents = useNeuralStore((s) => s.agents);
  const latestActivity = useNeuralStore((s) => s.latestActivity);
  const totalVerified = useNeuralStore((s) => s.totalVerified);
  const totalNuclear = useNeuralStore((s) => s.totalNuclear);
  const selectAgent = useNeuralStore((s) => s.selectAgent);

  return (
    <div className="pointer-events-none fixed bottom-0 left-0 right-0 z-20 border-t border-white/8 bg-black/55 backdrop-blur-lg">
      <div className="flex items-center gap-4 px-5 py-3">
        {/* fleet dots */}
        <div className="pointer-events-auto flex shrink-0 items-center gap-2">
          {agents.map((agent, i) => {
            const cfg = AGENT_CONFIG[i];
            return (
              <button
                key={agent.id}
                title={`${cfg.name} — ${agent.state.toUpperCase()}`}
                onClick={() => selectAgent(agent.id)}
                className="group relative flex flex-col items-center gap-1"
              >
                <span
                  className={`h-2 w-2 rounded-full transition-all duration-300 ${DOT_COLOR[agent.state]} ${agent.state !== 'idle' ? 'shadow-lg' : ''}`}
                  style={
                    agent.state !== 'idle'
                      ? { boxShadow: `0 0 6px ${cfg.color}` }
                      : undefined
                  }
                />
                <span className="hidden font-mono text-[7px] uppercase tracking-wider text-white/35 group-hover:block">
                  {cfg.name}
                </span>
              </button>
            );
          })}
        </div>

        {/* divider */}
        <div className="h-5 w-px shrink-0 bg-white/10" />

        {/* activity ticker */}
        <div className="min-w-0 flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            <motion.p
              key={latestActivity}
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -12, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="truncate font-mono text-[10px] tracking-wide text-white/45"
            >
              {latestActivity}
            </motion.p>
          </AnimatePresence>
        </div>

        {/* counters */}
        <div className="pointer-events-auto flex shrink-0 items-center gap-4">
          <div className="text-right">
            <p className="font-mono text-[8px] uppercase tracking-widest text-white/30">Verified</p>
            <p className="font-mono text-sm font-bold text-emerald-400">{totalVerified}</p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[8px] uppercase tracking-widest text-white/30">Nuclear</p>
            <p className="font-mono text-sm font-bold text-orange-500">{totalNuclear}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
