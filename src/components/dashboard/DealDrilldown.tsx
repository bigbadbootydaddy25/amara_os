"use client";

import { CanonicalDeal } from "@/core/schema/canonical";
import { GlassCard } from "@/components/ui/GlassCard";
import { ConfidenceBar } from "@/components/ui/ConfidenceBar";
import { formatCurrency, formatPct, timeAgo } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface DealDrilldownProps {
  deal: CanonicalDeal;
  onClose: () => void;
}

type Tab = "underwriting" | "buyer" | "closer" | "distress";

import { useState } from "react";

export function DealDrilldown({ deal, onClose }: DealDrilldownProps) {
  const [tab, setTab] = useState<Tab>("underwriting");

  const tabs: { id: Tab; label: string }[] = [
    { id: "underwriting", label: "UNDERWRITING" },
    { id: "buyer", label: "BUYER LANE" },
    { id: "closer", label: "CLOSER" },
    { id: "distress", label: "DISTRESS" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-[#1f2937]">
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              {deal.urgencyFlag && (
                <span className={cn(
                  "text-[9px] font-mono font-bold px-1.5 py-0.5 rounded tracking-wider",
                  deal.urgencyFlag === "HOT" ? "bg-green-400/10 text-green-400 border border-green-400/20" :
                  "bg-amber-400/10 text-amber-400 border border-amber-400/20"
                )}>
                  {deal.urgencyFlag}
                </span>
              )}
              <span className="text-[10px] font-mono text-[#00d4ff]">
                {deal.underwriting.dealType.replace("_", " ")}
              </span>
            </div>
            <h2 className="font-semibold text-slate-100">{deal.address}</h2>
            <div className="text-xs text-slate-500 font-mono">{deal.city}, {deal.state} {deal.zip} · {deal.market}</div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-600 hover:text-slate-400 transition-colors text-lg"
          >
            ✕
          </button>
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-4 gap-2 mt-3">
          {[
            { label: "MAO", value: formatCurrency(deal.underwriting.mao, true), color: "text-[#00d4ff]" },
            { label: "ARV", value: formatCurrency(deal.valuation.arvEstimate, true), color: "text-slate-200" },
            { label: "SPREAD", value: formatCurrency(deal.underwriting.projectedSpread, true), color: "text-green-400" },
            { label: "REHAB", value: formatCurrency(deal.valuation.rehabEstimate, true), color: "text-slate-300" },
          ].map((m) => (
            <div key={m.label} className="bg-[#0d1117] rounded p-2 border border-[#1f2937]">
              <div className="data-label mb-0.5">{m.label}</div>
              <div className={cn("font-mono font-bold text-sm", m.color)}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#1f2937]">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "flex-1 px-3 py-2.5 text-[10px] font-mono tracking-wider transition-colors",
              tab === t.id
                ? "text-[#00d4ff] border-b border-[#00d4ff] bg-[#00d4ff]/5"
                : "text-slate-500 hover:text-slate-400"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* UNDERWRITING TAB */}
        {tab === "underwriting" && (
          <div className="space-y-4">
            <GlassCard className="p-4">
              <div className="data-label mb-3">UNDERWRITING BREAKDOWN</div>
              <pre className="font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
                {deal.underwriting.dealType === "WHOLESALE_ASSIGNMENT"
                  ? [
                      `Investor Resale Max:  ${formatCurrency(deal.underwriting.buyerResaleMax)}`,
                      `- Assignment Fee:    ${formatCurrency(deal.underwriting.assignmentFee)}`,
                      `- Transaction Buffer: ~${formatCurrency((deal.underwriting.buyerResaleMax ?? 0) * 0.02)}`,
                      `- Safety Margin:     ~${formatCurrency((deal.underwriting.buyerResaleMax ?? 0) * 0.03)}`,
                      `= MAO to Seller:     ${formatCurrency(deal.underwriting.mao)}`,
                      ``,
                      `Projected Spread:    ${formatCurrency(deal.underwriting.projectedSpread)}`,
                    ].join("\n")
                  : [
                      `ARV:                ${formatCurrency(deal.valuation.arvEstimate)}`,
                      `- Rehab:            ${formatCurrency(deal.valuation.rehabEstimate)}`,
                      `- Holding Costs:    ${formatCurrency(deal.underwriting.holdingCosts)}`,
                      `- Close Sell Side:  ${formatCurrency(deal.underwriting.closingCostsSell)}`,
                      `- Flipper Margin:   ${formatCurrency(deal.underwriting.flipperMarginTarget)}`,
                      `= Flipper Max Buy:  ${formatCurrency(deal.underwriting.buyerResaleMax)}`,
                      `- Our Fee:          ${formatCurrency(deal.underwriting.assignmentFee)}`,
                      `= MAO to Seller:    ${formatCurrency(deal.underwriting.mao)}`,
                    ].join("\n")
                }
              </pre>
            </GlassCard>

            <GlassCard className="p-4">
              <div className="data-label mb-3">VALUATION BANDS</div>
              <div className="space-y-3">
                {[
                  { label: "ARV (After Repair)", low: deal.valuation.arvLow, high: deal.valuation.arvHigh, mid: deal.valuation.arvEstimate },
                  { label: "As-Is Value", low: deal.valuation.asIsLow, high: deal.valuation.asIsHigh, mid: deal.valuation.asIsEstimate },
                  { label: "Investor Resale", low: deal.valuation.investorResaleLow, high: deal.valuation.investorResaleHigh, mid: deal.valuation.investorResaleEstimate },
                  { label: "Rehab Estimate", low: deal.valuation.rehabLow, high: deal.valuation.rehabHigh, mid: deal.valuation.rehabEstimate },
                ].map((v) => (
                  <div key={v.label} className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">{v.label}</span>
                    <span className="font-mono text-xs text-slate-200">
                      {formatCurrency(v.low, true)} – {formatCurrency(v.high, true)}
                      <span className="text-[#00d4ff] ml-2">({formatCurrency(v.mid, true)})</span>
                    </span>
                  </div>
                ))}
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <div className="data-label mb-3">PROPERTY DETAILS</div>
              <div className="grid grid-cols-2 gap-y-2 text-xs">
                {[
                  ["Address", deal.address],
                  ["Type", deal.propertyType],
                  ["Beds/Baths", `${deal.beds}bd / ${deal.baths}ba`],
                  ["Sq Ft", deal.livingAreaSqft?.toLocaleString() ?? "—"],
                  ["Year Built", deal.yearBuilt ?? "—"],
                  ["List Price", formatCurrency(deal.listPrice)],
                  ["DOM", `${deal.dom} days`],
                  ["Source", deal.sources.join(", ")],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex gap-2">
                    <span className="text-slate-600 w-24 shrink-0">{k}</span>
                    <span className="text-slate-300 font-mono">{v}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        )}

        {/* BUYER LANE TAB */}
        {tab === "buyer" && (
          <div className="space-y-4">
            <GlassCard glow="deal" className="p-4">
              <div className="data-label mb-3">EXIT BUYER LANE</div>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Buyer Class</span>
                  <span className="font-mono text-sm text-green-400 font-semibold">
                    {deal.buyerLane.buyerClass}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Active Buyers in ZIP</span>
                  <span className="font-mono text-sm text-slate-200">
                    {deal.buyerLane.matchedBuyerCount} validated
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Est. Days to Assign</span>
                  <span className="font-mono text-sm text-slate-200">
                    ~{deal.buyerLane.estimatedDaysToAssign} days
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Weekly Closing Potential</span>
                  <span className={cn("font-mono text-sm font-semibold", deal.buyerLane.weeklyClosingPotential ? "text-green-400" : "text-slate-500")}>
                    {deal.buyerLane.weeklyClosingPotential ? "YES" : "NO"}
                  </span>
                </div>
              </div>
              <div className="mt-4">
                <ConfidenceBar score={deal.buyerLane.exitConfidenceScore} label="EXIT CONFIDENCE" />
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <div className="data-label mb-3">ACTIVE BUYER ZIPs</div>
              <div className="flex flex-wrap gap-2">
                {deal.buyerLane.matchedBuyerZIPs.map((zip) => (
                  <span key={zip} className="font-mono text-xs text-[#00d4ff] bg-[#00d4ff]/5 border border-[#00d4ff]/10 px-2 py-1 rounded">
                    {zip}
                  </span>
                ))}
              </div>
            </GlassCard>
          </div>
        )}

        {/* CLOSER TAB */}
        {tab === "closer" && (
          <div className="space-y-3">
            {[
              { label: "SELLER PAIN PROFILE", value: deal.closeStrategy.sellerPainProfile, color: "text-amber-400" },
              { label: "LIKELY MOTIVATION", value: deal.closeStrategy.likelyMotivation },
              { label: "NEGOTIATION ANGLE", value: deal.closeStrategy.negotiationAngle },
              { label: "OPENING APPROACH", value: deal.closeStrategy.openingApproach },
              { label: "ANCHOR PRICE LOGIC", value: deal.closeStrategy.anchorPriceLogic, color: "text-[#00d4ff]" },
              { label: "OBJECTION RESPONSE", value: deal.closeStrategy.objectionResponse },
              { label: "FOLLOW-UP SCHEDULE", value: deal.closeStrategy.followUpSchedule },
              { label: "WALK-AWAY TRIGGER", value: deal.closeStrategy.walkAwayTrigger, color: "text-red-400" },
              { label: "COACHING NOTE", value: deal.closeStrategy.coachingNote, color: "text-green-400" },
            ].map((item) => (
              <GlassCard key={item.label} className="p-3">
                <div className="data-label mb-1.5">{item.label}</div>
                <div className={cn("text-xs leading-relaxed", item.color ?? "text-slate-300")}>
                  {item.value}
                </div>
              </GlassCard>
            ))}

            {/* Next action */}
            <GlassCard glow="signal" className="p-3">
              <div className="data-label mb-1.5">NEXT ACTION</div>
              <div className="text-xs text-[#00d4ff] leading-relaxed font-semibold">
                {deal.nextAction}
              </div>
              {deal.nextActionDueDate && (
                <div className="text-[10px] font-mono text-slate-500 mt-2">
                  DUE: {new Date(deal.nextActionDueDate).toLocaleString()}
                </div>
              )}
            </GlassCard>
          </div>
        )}

        {/* DISTRESS TAB */}
        {tab === "distress" && (
          <div className="space-y-4">
            <GlassCard className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="data-label">DISTRESS SCORE</div>
                <div className="font-mono font-bold text-2xl text-amber-400">
                  {deal.distress.totalDistressScore}
                </div>
              </div>
              <ConfidenceBar score={deal.distress.totalDistressScore} />
            </GlassCard>

            <GlassCard className="p-4">
              <div className="data-label mb-3">DISTRESS FLAGS</div>
              <div className="grid grid-cols-2 gap-y-2 text-xs">
                {[
                  ["Price Reduced", deal.distress.priceReduced],
                  ["Reduction Count", deal.distress.priceReductionCount],
                  ["DOM Bucket", deal.distress.domBucket],
                  ["Absentee Owner", deal.distress.absenteeOwner],
                  ["Tax Delinquent", deal.distress.taxDelinquent],
                  ["Preforeclosure", deal.distress.preforeclosure],
                  ["Foreclosure", deal.distress.foreclosure],
                  ["Probate/Estate", deal.distress.probate || deal.distress.estate],
                  ["Vacant", deal.distress.vacancy],
                  ["Tenant Occupied", deal.distress.tenantOccupied],
                  ["Landlord Fatigue", deal.distress.landlordFatigue],
                  ["Liens", deal.distress.liens],
                ].map(([k, v]) => (
                  <div key={k as string} className="flex gap-2 items-center">
                    <span className={cn("w-2 h-2 rounded-full shrink-0", v ? "bg-amber-400" : "bg-[#1f2937]")} />
                    <span className="text-slate-400">{k as string}</span>
                    <span className={cn("font-mono ml-auto", v ? "text-amber-400" : "text-slate-600")}>
                      {typeof v === "number" ? v : v ? "YES" : "NO"}
                    </span>
                  </div>
                ))}
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <div className="data-label mb-3">MATCHED DISTRESS KEYWORDS</div>
              <div className="flex flex-wrap gap-1.5">
                {deal.distress.distressKeywordsFound.map((kw) => (
                  <span
                    key={kw}
                    className="text-[10px] font-mono text-amber-400 bg-amber-400/5 border border-amber-400/15 px-2 py-0.5 rounded"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <div className="data-label mb-3">PRICE HISTORY</div>
              <div className="space-y-2">
                {deal.priceHistory.map((ph, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="font-mono text-slate-500">{ph.date}</span>
                    <span className={cn(
                      "px-1.5 py-0.5 rounded font-mono text-[10px]",
                      ph.event === "REDUCED" ? "bg-red-400/10 text-red-400" :
                      ph.event === "LISTED" ? "bg-[#1f2937] text-slate-400" :
                      "bg-green-400/10 text-green-400"
                    )}>
                      {ph.event}
                    </span>
                    <span className="font-mono text-slate-200 font-semibold">
                      {formatCurrency(ph.price)}
                    </span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        )}
      </div>
    </div>
  );
}
