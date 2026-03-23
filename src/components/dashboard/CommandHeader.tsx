"use client";

import { StatusPulse } from "@/components/ui/StatusPulse";
import { MetricWidget } from "@/components/ui/MetricWidget";
import { formatCurrency } from "@/lib/utils";

interface CommandHeaderProps {
  stats: {
    totalDeals: number;
    hotDeals: number;
    warmDeals: number;
    totalPotentialSpread: number;
    activeMarkets: number;
    lastUpdated: string;
  };
  scanActive: boolean;
}

export function CommandHeader({ stats, scanActive }: CommandHeaderProps) {
  const time = new Date().toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return (
    <header className="border-b border-[#1f2937] bg-[#080b12]/90 backdrop-blur-sm sticky top-0 z-50">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-[#111827]">
        {/* Brand */}
        <div className="flex items-center gap-4">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-[#00d4ff] font-mono font-bold text-lg tracking-[0.15em]">
                AMARA OS
              </span>
              <span className="text-[10px] font-mono text-slate-600 tracking-widest border border-[#1f2937] px-1.5 py-0.5 rounded">
                v0.1
              </span>
            </div>
            <span className="text-[10px] font-mono text-slate-600 tracking-[0.2em] uppercase">
              ACES N 8S — ACQUISITIONS INTELLIGENCE
            </span>
          </div>
        </div>

        {/* System status */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <StatusPulse
              color={scanActive ? "green" : "gray"}
              label={scanActive ? "SCAN ACTIVE" : "SCAN IDLE"}
            />
            <StatusPulse color="signal" label="ENGINE ONLINE" />
          </div>
          <div className="text-right">
            <div className="font-mono text-xs text-[#00d4ff]">{time}</div>
            <div className="font-mono text-[10px] text-slate-600">
              {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
            </div>
          </div>
        </div>
      </div>

      {/* Metrics bar */}
      <div className="flex items-center gap-8 px-6 py-3">
        <div className="flex items-center gap-6 divide-x divide-[#1f2937]">
          <MetricWidget
            label="DEAL FEED"
            value={stats.totalDeals}
            sub="qualified deals"
            highlight
          />
          <div className="pl-6">
            <MetricWidget
              label="HOT"
              value={stats.hotDeals}
              sub="move today"
            />
          </div>
          <div className="pl-6">
            <MetricWidget
              label="WARM"
              value={stats.warmDeals}
              sub="48hr window"
            />
          </div>
          <div className="pl-6">
            <MetricWidget
              label="POTENTIAL SPREAD"
              value={formatCurrency(stats.totalPotentialSpread, true)}
              sub="active pipeline"
              highlight
            />
          </div>
          <div className="pl-6">
            <MetricWidget
              label="ACTIVE MARKETS"
              value={stats.activeMarkets}
              sub="in deal feed"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <div className="h-8 w-px bg-[#1f2937]" />
          <div className="text-right">
            <div className="data-label">LAST SCAN</div>
            <div className="font-mono text-xs text-slate-400">
              {new Date(stats.lastUpdated).toLocaleTimeString()}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
