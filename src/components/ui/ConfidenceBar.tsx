"use client";

import { cn } from "@/lib/utils";

interface ConfidenceBarProps {
  score: number;     // 0–100
  label?: string;
  showScore?: boolean;
  className?: string;
}

export function ConfidenceBar({ score, label, showScore = true, className }: ConfidenceBarProps) {
  const color =
    score >= 70 ? "bg-green-400" :
    score >= 45 ? "bg-amber-400" :
    "bg-slate-600";

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label && (
        <div className="flex justify-between items-center">
          <span className="data-label">{label}</span>
          {showScore && (
            <span className={cn("font-mono text-xs font-semibold", score >= 70 ? "text-green-400" : score >= 45 ? "text-amber-400" : "text-slate-500")}>
              {score}
            </span>
          )}
        </div>
      )}
      <div className="h-[3px] bg-[#1e293b] rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color)}
          style={{ width: `${Math.min(100, score)}%` }}
        />
      </div>
    </div>
  );
}
