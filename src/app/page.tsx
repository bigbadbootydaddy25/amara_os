"use client";

import { useState, useEffect } from "react";
import { CanonicalDeal } from "@/core/schema/canonical";
import { CommandHeader } from "@/components/dashboard/CommandHeader";
import { DealCard } from "@/components/dashboard/DealCard";
import { DealDrilldown } from "@/components/dashboard/DealDrilldown";
import { MarketIntelPanel } from "@/components/dashboard/MarketIntelPanel";
import { BuyerIntelPanel } from "@/components/dashboard/BuyerIntelPanel";
import { ScanStatusPanel } from "@/components/dashboard/ScanStatusPanel";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatusPulse } from "@/components/ui/StatusPulse";
import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";

type SidebarPanel = "markets" | "buyers" | "scan";

export default function MissionControl() {
  const [deals, setDeals] = useState<CanonicalDeal[]>([]);
  const [stats, setStats] = useState({
    totalDeals: 0,
    hotDeals: 0,
    warmDeals: 0,
    totalPotentialSpread: 0,
    activeMarkets: 0,
    topMarket: "—",
    lastUpdated: new Date().toISOString(),
  });
  const [selectedDeal, setSelectedDeal] = useState<CanonicalDeal | null>(null);
  const [activePanel, setActivePanel] = useState<SidebarPanel>("markets");
  const [filterUrgency, setFilterUrgency] = useState<"ALL" | "HOT" | "WARM">("ALL");
  const [filterMarket, setFilterMarket] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    try {
      const [dealsRes, statsRes] = await Promise.all([
        fetch("/api/deals"),
        fetch("/api/stats"),
      ]);
      const { deals: d } = await dealsRes.json();
      const s = await statsRes.json();
      setDeals(d);
      setStats(s);
    } catch (err) {
      console.error("Failed to fetch data:", err);
    } finally {
      setLoading(false);
    }
  }

  const filteredDeals = deals
    .filter((d) => {
      if (filterUrgency !== "ALL" && d.urgencyFlag !== filterUrgency) return false;
      if (filterMarket !== "ALL" && d.market !== filterMarket) return false;
      return true;
    })
    .sort((a, b) => {
      // HOT first, then by confidence score
      const urgencyRank = { HOT: 3, WARM: 2, WATCH: 1, null: 0 };
      const rankA = urgencyRank[a.urgencyFlag ?? "null"] ?? 0;
      const rankB = urgencyRank[b.urgencyFlag ?? "null"] ?? 0;
      if (rankA !== rankB) return rankB - rankA;
      return b.closeConfidenceScore - a.closeConfidenceScore;
    });

  const markets = ["ALL", ...new Set(deals.map((d) => d.market))];

  return (
    <div className="min-h-screen bg-[#050508] scanlines">
      {/* Scan line effect */}
      <div className="scan-line" />

      {/* Grid background */}
      <div className="fixed inset-0 grid-bg opacity-40 pointer-events-none" />

      {/* Header */}
      <CommandHeader stats={stats} scanActive={true} />

      {/* Main layout */}
      <div className="flex h-[calc(100vh-118px)]">

        {/* Left sidebar — panels */}
        <div className="w-80 shrink-0 border-r border-[#1f2937] flex flex-col">
          {/* Panel selector */}
          <div className="flex border-b border-[#1f2937]">
            {(["markets", "buyers", "scan"] as SidebarPanel[]).map((panel) => (
              <button
                key={panel}
                onClick={() => setActivePanel(panel)}
                className={cn(
                  "flex-1 py-2.5 text-[9px] font-mono tracking-widest uppercase transition-colors",
                  activePanel === panel
                    ? "text-[#00d4ff] bg-[#00d4ff]/5 border-b border-[#00d4ff]"
                    : "text-slate-600 hover:text-slate-400"
                )}
              >
                {panel}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {activePanel === "markets" && <MarketIntelPanel />}
            {activePanel === "buyers" && <BuyerIntelPanel />}
            {activePanel === "scan" && <ScanStatusPanel />}
          </div>
        </div>

        {/* Center — Deal Feed (Strike Zone) */}
        <div className="flex-1 flex flex-col overflow-hidden border-r border-[#1f2937]">
          {/* Strike Zone header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1f2937] bg-[#080b12]/50">
            <div className="flex items-center gap-3">
              <div>
                <div className="data-label mb-0">STRIKE ZONE</div>
                <div className="text-[10px] text-slate-500">
                  {filteredDeals.length} qualified deal{filteredDeals.length !== 1 ? "s" : ""} · exits confirmed · spread validated
                </div>
              </div>
              <StatusPulse color="green" />
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2">
              {/* Urgency filter */}
              <div className="flex gap-1">
                {(["ALL", "HOT", "WARM"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilterUrgency(f)}
                    className={cn(
                      "px-2 py-1 rounded text-[9px] font-mono tracking-wider transition-colors",
                      filterUrgency === f
                        ? f === "HOT" ? "bg-green-400/15 text-green-400 border border-green-400/30"
                          : f === "WARM" ? "bg-amber-400/15 text-amber-400 border border-amber-400/30"
                          : "bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20"
                        : "text-slate-600 border border-[#1f2937] hover:border-slate-600"
                    )}
                  >
                    {f}
                  </button>
                ))}
              </div>

              {/* Market filter */}
              <select
                value={filterMarket}
                onChange={(e) => setFilterMarket(e.target.value)}
                className="bg-[#0d1117] border border-[#1f2937] rounded px-2 py-1 text-[10px] font-mono text-slate-400 focus:outline-none focus:border-[#00d4ff]/30"
              >
                {markets.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Deal feed */}
          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <LoadingState />
            ) : filteredDeals.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="space-y-3">
                {filteredDeals.map((deal) => (
                  <DealCard
                    key={deal.id}
                    deal={deal}
                    selected={selectedDeal?.id === deal.id}
                    onSelect={setSelectedDeal}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right panel — Drilldown / Intel */}
        <div className="w-[380px] shrink-0 overflow-hidden flex flex-col bg-[#080b12]/50">
          {selectedDeal ? (
            <DealDrilldown
              deal={selectedDeal}
              onClose={() => setSelectedDeal(null)}
            />
          ) : (
            <EmptyDrilldown onPickDeal={() => {
              if (filteredDeals[0]) setSelectedDeal(filteredDeals[0]);
            }} />
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SUPPORT COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────
function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
      <StatusPulse color="signal" label="SCANNING MARKETS" />
      <div className="text-xs text-slate-600 font-mono">Running deal engines...</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-8">
      <div className="text-[#00d4ff] text-4xl opacity-20">◉</div>
      <div className="font-mono text-slate-500 text-sm">
        NO DEALS IN STRIKE ZONE
      </div>
      <div className="text-xs text-slate-600 max-w-xs">
        AMARA is scanning silently. When a deal passes all gates — exit path confirmed, distress validated, spread real — it will appear here.
      </div>
      <div className="text-[10px] font-mono text-slate-700">
        AMARA watches so you don't have to.
      </div>
    </div>
  );
}

function EmptyDrilldown({ onPickDeal }: { onPickDeal: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-6 text-center">
      <div className="text-[#00d4ff] text-3xl opacity-10">▶</div>
      <div className="font-mono text-[11px] text-slate-600 tracking-wider">
        SELECT A DEAL
      </div>
      <div className="text-xs text-slate-700 max-w-48">
        Click any deal card to open deep underwriting, buyer intel, and close coaching.
      </div>
      <button
        onClick={onPickDeal}
        className="mt-4 text-[10px] font-mono text-[#00d4ff] border border-[#00d4ff]/20 px-4 py-2 rounded hover:bg-[#00d4ff]/5 transition-colors"
      >
        OPEN TOP DEAL
      </button>
    </div>
  );
}
