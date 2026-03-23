"use client";

import { GlassCard } from "@/components/ui/GlassCard";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";

const BUYER_LANES = [
  {
    market: "DFW",
    zip: "75228",
    buyerClass: "FLIPPER",
    activeBuyers: 14,
    repeatBuyers: 8,
    avgDaysClose: 12,
    demandStrength: "HOT" as const,
    priceRange: "$70K–$280K",
  },
  {
    market: "Phoenix",
    zip: "85031",
    buyerClass: "FLIPPER",
    activeBuyers: 15,
    repeatBuyers: 9,
    avgDaysClose: 11,
    demandStrength: "HOT" as const,
    priceRange: "$100K–$350K",
  },
  {
    market: "Atlanta",
    zip: "30310",
    buyerClass: "FLIPPER",
    activeBuyers: 16,
    repeatBuyers: 10,
    avgDaysClose: 10,
    demandStrength: "HOT" as const,
    priceRange: "$50K–$220K",
  },
  {
    market: "DFW",
    zip: "76104",
    buyerClass: "FLIPPER",
    activeBuyers: 9,
    repeatBuyers: 5,
    avgDaysClose: 15,
    demandStrength: "HOT" as const,
    priceRange: "$60K–$200K",
  },
  {
    market: "Cleveland",
    zip: "44105",
    buyerClass: "LANDLORD",
    activeBuyers: 18,
    repeatBuyers: 12,
    avgDaysClose: 8,
    demandStrength: "HOT" as const,
    priceRange: "$20K–$95K",
  },
  {
    market: "Houston",
    zip: "77051",
    buyerClass: "FLIPPER",
    activeBuyers: 12,
    repeatBuyers: 7,
    avgDaysClose: 13,
    demandStrength: "HOT" as const,
    priceRange: "$60K–$200K",
  },
];

export function BuyerIntelPanel() {
  const hotLanes = BUYER_LANES.filter((l) => l.demandStrength === "HOT");

  return (
    <GlassCard className="p-4 h-full flex flex-col">
      <div className="mb-4">
        <div className="data-label mb-0.5">BUYER INTELLIGENCE</div>
        <div className="text-xs text-slate-400">Active exit lanes · Repeat buyer activity</div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {hotLanes.map((lane, i) => (
          <div
            key={i}
            className="bg-[#0d1117] rounded p-3 border border-[#1f2937] hover:border-[#00d4ff]/15 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-green-400/10 text-green-400 border border-green-400/20">
                  HOT
                </span>
                <span className="text-xs font-mono text-slate-300">{lane.market} · {lane.zip}</span>
              </div>
              <span className="text-[10px] font-mono text-slate-500">{lane.buyerClass}</span>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center mb-2">
              <div>
                <div className="data-label">BUYERS</div>
                <div className="font-mono text-sm font-bold text-[#00d4ff]">{lane.activeBuyers}</div>
              </div>
              <div>
                <div className="data-label">REPEAT</div>
                <div className="font-mono text-sm font-bold text-green-400">{lane.repeatBuyers}</div>
              </div>
              <div>
                <div className="data-label">AVG CLOSE</div>
                <div className="font-mono text-sm font-bold text-slate-200">{lane.avgDaysClose}d</div>
              </div>
            </div>

            <div className="flex items-center justify-between text-[10px]">
              <span className="font-mono text-slate-500">{lane.priceRange}</span>
              <span className="font-mono text-slate-500">
                {lane.repeatBuyers}/{lane.activeBuyers} repeat
              </span>
            </div>

            <div className="mt-2">
              <ConfidenceBar
                score={Math.round((lane.repeatBuyers / lane.activeBuyers) * 100)}
                showScore={false}
              />
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
