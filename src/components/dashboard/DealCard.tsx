"use client";

import { CanonicalDeal } from "@/core/schema/canonical";
import { GlassCard } from "@/components/ui/GlassCard";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { formatCurrency, timeAgo, truncate } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface DealCardProps {
  deal: CanonicalDeal;
  selected?: boolean;
  onSelect: (deal: CanonicalDeal) => void;
}

export function DealCard({ deal, selected, onSelect }: DealCardProps) {
  const isHot = deal.urgencyFlag === "HOT";
  const isWarm = deal.urgencyFlag === "WARM";

  const urgencyBadge = {
    HOT: { label: "HOT", class: "bg-green-400/10 text-green-400 border border-green-400/20" },
    WARM: { label: "WARM", class: "bg-amber-400/10 text-amber-400 border border-amber-400/20" },
    WATCH: { label: "WATCH", class: "bg-blue-400/10 text-blue-400 border border-blue-400/20" },
  };

  const badge = deal.urgencyFlag ? urgencyBadge[deal.urgencyFlag] : null;

  const dealTypeLabel = {
    WHOLESALE_ASSIGNMENT: "WHOLESALE",
    FLIP: "FLIP",
    BRRRR: "BRRRR",
    LAND_SUBDIVISION: "LAND",
    DEAD_PAPER: "DEAD PAPER",
    CREATIVE_FINANCE: "CREATIVE FIN.",
    UNKNOWN: "—",
  }[deal.underwriting.dealType];

  const exitBuyerLabel = {
    FLIPPER: "FLIPPER EXIT",
    LANDLORD: "LANDLORD EXIT",
    DEVELOPER: "DEVELOPER EXIT",
    OWNER_OCCUPANT: "RETAIL EXIT",
    UNKNOWN: "EXIT TBD",
  }[deal.buyerLane.buyerClass];

  return (
    <GlassCard
      glow={isHot ? "deal" : isWarm ? "amber" : "none"}
      onClick={() => onSelect(deal)}
      className={cn(
        "p-4 hover-glow",
        selected && "ring-1 ring-[#00d4ff]/30 border-[rgba(0,212,255,0.2)]"
      )}
    >
      {/* Top row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {badge && (
              <span className={cn("text-[9px] font-mono font-bold px-1.5 py-0.5 rounded tracking-wider", badge.class)}>
                {badge.label}
              </span>
            )}
            <span className="text-[10px] font-mono text-[#00d4ff] tracking-wider">{dealTypeLabel}</span>
            <span className="text-[#1f2937]">·</span>
            <span className="text-[10px] font-mono text-slate-500">{deal.market}</span>
          </div>
          <div className="font-semibold text-slate-100 text-sm truncate">{deal.address}</div>
          <div className="text-xs text-slate-500 font-mono">{deal.city}, {deal.state} {deal.zip}</div>
        </div>

        <div className="text-right ml-3 shrink-0">
          <div className="data-label mb-0.5">MAO</div>
          <div className="font-mono font-bold text-[#00d4ff] text-base">
            {formatCurrency(deal.underwriting.mao, true)}
          </div>
        </div>
      </div>

      {/* Key metrics row */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <div className="data-label mb-0.5">ARV</div>
          <div className="font-mono text-sm text-slate-200">
            {formatCurrency(deal.valuation.arvEstimate, true)}
          </div>
        </div>
        <div>
          <div className="data-label mb-0.5">SPREAD</div>
          <div className="font-mono text-sm font-semibold text-green-400">
            {formatCurrency(deal.underwriting.projectedSpread, true)}
          </div>
        </div>
        <div>
          <div className="data-label mb-0.5">REHAB</div>
          <div className="font-mono text-sm text-slate-300">
            {formatCurrency(deal.valuation.rehabEstimate, true)}
          </div>
        </div>
      </div>

      {/* Exit buyer / DOM row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#1f2937] text-slate-400">
            {exitBuyerLabel}
          </span>
          <span className="text-[9px] font-mono text-slate-500">
            {deal.buyerLane.matchedBuyerCount} buyers · ~{deal.buyerLane.estimatedDaysToAssign}d to assign
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            "text-[9px] font-mono px-1.5 py-0.5 rounded",
            deal.distress.domDays >= 90 ? "text-red-400 bg-red-400/10" :
            deal.distress.domDays >= 60 ? "text-amber-400 bg-amber-400/10" :
            "text-slate-500 bg-[#1f2937]"
          )}>
            {deal.distress.domDays}d DOM
          </span>
          {deal.distress.priceReduced && (
            <span className="text-[9px] font-mono text-red-400 bg-red-400/10 px-1.5 py-0.5 rounded">
              -{Math.round(deal.distress.priceReductionTotalPct * 100)}% cut
            </span>
          )}
        </div>
      </div>

      {/* Distress tags */}
      <div className="flex flex-wrap gap-1 mb-3">
        {deal.distress.distressKeywordsFound.slice(0, 4).map((kw) => (
          <span
            key={kw}
            className="text-[9px] font-mono text-amber-400/70 bg-amber-400/5 border border-amber-400/10 px-1.5 py-0.5 rounded"
          >
            {kw}
          </span>
        ))}
        {deal.distress.distressKeywordsFound.length > 4 && (
          <span className="text-[9px] font-mono text-slate-600">
            +{deal.distress.distressKeywordsFound.length - 4}
          </span>
        )}
      </div>

      {/* Confidence bars */}
      <div className="space-y-1.5 mb-3">
        <ConfidenceBar score={deal.closeConfidenceScore} label="CLOSE CONFIDENCE" />
        <ConfidenceBar score={deal.distress.totalDistressScore} label="DISTRESS SCORE" />
      </div>

      {/* Next action */}
      <div className="border-t border-[#1f2937] pt-2 mt-1">
        <div className="data-label mb-1">NEXT ACTION</div>
        <div className="text-xs text-slate-300 leading-relaxed">
          {truncate(deal.nextAction, 120)}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] font-mono text-slate-600">
          {deal.sources.join(" + ").toUpperCase()}
        </span>
        <span className="text-[10px] font-mono text-slate-600">
          {timeAgo(deal.lastScannedAt)}
        </span>
      </div>
    </GlassCard>
  );
}
