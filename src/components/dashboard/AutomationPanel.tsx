'use client';

import { useState, useEffect, useCallback } from 'react';
import type { AutomationState } from '@/types/real-estate';

export default function AutomationPanel() {
  const [state, setState] = useState<AutomationState>({ isRunning: false, log: [] });
  const [loading, setLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    const res = await fetch('/api/scan');
    if (res.ok) {
      const data = (await res.json()) as { state: AutomationState };
      setState(data.state);
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
    const interval = setInterval(() => void fetchStatus(), 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const triggerScan = async () => {
    setLoading(true);
    await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    await fetchStatus();
    setLoading(false);
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-zinc-100">Automation Loop</h3>
          {state.lastScanAt && (
            <p className="text-xs text-zinc-500">
              Last scan: {new Date(state.lastScanAt).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={() => void triggerScan()}
          disabled={state.isRunning || loading}
          className={`px-4 py-2 rounded text-sm font-medium transition-colors ${
            state.isRunning || loading
              ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
              : 'bg-cyan-500 hover:bg-cyan-400 text-black'
          }`}
        >
          {state.isRunning ? 'Running…' : 'Run Scan'}
        </button>
      </div>

      {/* Current step */}
      {state.currentStep && (
        <div className="flex items-center gap-2 text-sm text-cyan-300">
          <span className="inline-block h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
          {state.currentStep}
        </div>
      )}

      {/* Log */}
      {state.log.length > 0 && (
        <div className="bg-zinc-950 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-xs text-zinc-400 space-y-0.5">
          {state.log.map((entry, i) => (
            <div key={i} className={entry.includes('✓') ? 'text-emerald-400' : entry.includes('✗') ? 'text-red-400' : ''}>
              {entry}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
