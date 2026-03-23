"use client";

import { GlassCard } from "@/components/ui/GlassCard";
import { StatusPulse } from "@/components/ui/StatusPulse";
import { SEEDED_MARKET_SCORES } from "@/core/engines/market/marketSelector";
import { cn } from "@/lib/utils";

interface MarketIntelPanelProps {
  onSelectMarket?: (marketId: string) => void;
  selectedMarket?: string;
}

export function MarketIntelPanel({ onSelectMarket, selectedMarket }: MarketIntelPanelProps) {
  const tier1 = SEEDED_MARKET_SCORES.filter((m) => m.tier === "TIER_1_PRIORITY");
  const tier2 = SEEDED_MARKET_SCORES.filter((m) => m.tier === "TIER_2_ACTIVE");

  return (
    <GlassCard className="p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="data-label mb-0.5">MARKET INTELLIGENCE</div>
          <div className="text-xs text-slate-400">Weekly closing potential rankings</div>
        </div>
        <StatusPulse color="green" label="LIVE" />
      </div>

      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        {/* Tier 1 */}
        <div className="data-label mb-2 mt-1">TIER 1 — PRIORITY MARKETS</div>
        {tier1.map((market) => (
          <MarketRow
            key={market.id}
            market={market}
            selected={selectedMarket === market.id}
            onClick={() => onSelectMarket?.(market.id)}
          />
        ))}

        {/* Tier 2 */}
        <div className="data-label mb-2 mt-4">TIER 2 — ACTIVE MARKETS</div>
        {tier2.map((market) => (
          <MarketRow
            key={market.id}
            market={market}
            selected={selectedMarket === market.id}
            onClick={() => onSelectMarket?.(market.id)}
          />
        ))}
      </div>
    </GlassCard>
  );
}

function MarketRow({ market, selected, onClick }: {
  market: typeof SEEDED_MARKET_SCORES[0];
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center justify-between px-3 py-2 rounded cursor-pointer transition-all",
        selected
          ? "bg-[#00d4ff]/10 border border-[#00d4ff]/20"
          : "hover:bg-[#0d1117] border border-transparent"
      )}
    >
      <div className="flex items-center gap-3">
        <div className={cn(
          "w-1.5 h-1.5 rounded-full shrink-0",
          market.cashBuyerDensity === "HIGH" ? "bg-green-400" : "bg-amber-400"
        )} />
        <div>
          <div className="text-sm font-semibold text-slate-200">{market.label}</div>
          <div className="text-[10px] font-mono text-slate-600">{market.state}</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right">
          <div className="data-label">DOM</div>
          <div className="font-mono text-xs text-slate-300">{market.avgDOMOnDistress}d</div>
        </div>
        <div className="text-right">
          <div className="data-label">SCORE</div>
          <div className={cn(
            "font-mono text-sm font-bold",
            market.weeklyClosingScore >= 85 ? "text-green-400" :
            market.weeklyClosingScore >= 70 ? "text-amber-400" : "text-slate-400"
          )}>
            {market.weeklyClosingScore}
          </div>
        </div>
      </div>
    </div>
  );
}
