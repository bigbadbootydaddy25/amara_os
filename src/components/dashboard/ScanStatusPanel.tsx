"use client";

import { GlassCard } from "@/components/ui/GlassCard";
import { StatusPulse } from "@/components/ui/StatusPulse";
import { cn } from "@/lib/utils";

const SCAN_SOURCES = [
  { name: "Zillow", status: "SCANNING" as const, lastSync: "2 min ago", recordsFound: 847, dealsFound: 3 },
  { name: "PropStream", status: "READY" as const, lastSync: "8 min ago", recordsFound: 1204, dealsFound: 1 },
  { name: "Propelio", status: "READY" as const, lastSync: "15 min ago", recordsFound: 312, dealsFound: 0 },
  { name: "Public Records", status: "OFFLINE" as const, lastSync: "2h ago", recordsFound: 0, dealsFound: 0 },
  { name: "XLeads", status: "PENDING" as const, lastSync: "Not configured", recordsFound: 0, dealsFound: 0 },
];

const SCAN_MARKETS = [
  { label: "DFW", status: "ACTIVE" as const, deals: 2, scanned: 1204 },
  { label: "Phoenix", status: "ACTIVE" as const, deals: 1, scanned: 847 },
  { label: "Houston", status: "QUEUED" as const, deals: 0, scanned: 0 },
  { label: "Atlanta", status: "QUEUED" as const, deals: 0, scanned: 0 },
  { label: "Cleveland", status: "QUEUED" as const, deals: 0, scanned: 0 },
];

export function ScanStatusPanel() {
  return (
    <GlassCard className="p-4 flex flex-col gap-4">
      <div>
        <div className="data-label mb-0.5">SCAN & SOURCE STATUS</div>
        <div className="text-xs text-slate-400">Live source health · market scan state</div>
      </div>

      {/* Source health */}
      <div>
        <div className="data-label mb-2">SOURCE ADAPTERS</div>
        <div className="space-y-1.5">
          {SCAN_SOURCES.map((src) => (
            <div key={src.name} className="flex items-center justify-between bg-[#0d1117] rounded px-3 py-2 border border-[#1f2937]">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "w-1.5 h-1.5 rounded-full",
                  src.status === "SCANNING" ? "bg-green-400 animate-pulse" :
                  src.status === "READY" ? "bg-[#00d4ff]" :
                  src.status === "OFFLINE" ? "bg-red-400" : "bg-slate-600"
                )} />
                <span className="text-xs text-slate-300">{src.name}</span>
              </div>
              <div className="flex items-center gap-4 text-right">
                <div>
                  <div className="data-label">RECORDS</div>
                  <div className="font-mono text-xs text-slate-400">{src.recordsFound.toLocaleString()}</div>
                </div>
                <div>
                  <div className="data-label">DEALS</div>
                  <div className={cn("font-mono text-xs font-bold", src.dealsFound > 0 ? "text-green-400" : "text-slate-600")}>
                    {src.dealsFound}
                  </div>
                </div>
                <div>
                  <div className="data-label">STATUS</div>
                  <div className={cn(
                    "font-mono text-[10px]",
                    src.status === "SCANNING" ? "text-green-400" :
                    src.status === "READY" ? "text-[#00d4ff]" :
                    src.status === "OFFLINE" ? "text-red-400" : "text-slate-500"
                  )}>
                    {src.status}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Market scan status */}
      <div>
        <div className="data-label mb-2">MARKET SCAN STATUS</div>
        <div className="space-y-1.5">
          {SCAN_MARKETS.map((mkt) => (
            <div key={mkt.label} className="flex items-center justify-between px-3 py-1.5 rounded bg-[#0d1117] border border-[#1f2937]">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "w-1.5 h-1.5 rounded-full",
                  mkt.status === "ACTIVE" ? "bg-green-400" : "bg-slate-600"
                )} />
                <span className="font-mono text-xs text-slate-300">{mkt.label}</span>
              </div>
              <div className="flex items-center gap-4 text-right">
                <span className="font-mono text-[10px] text-slate-500">{mkt.scanned.toLocaleString()} scanned</span>
                <span className={cn("font-mono text-xs font-bold", mkt.deals > 0 ? "text-green-400" : "text-slate-600")}>
                  {mkt.deals} deal{mkt.deals !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  );
}
