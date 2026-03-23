"use client";

import { cn } from "@/lib/utils";

interface MetricWidgetProps {
  label: string;
  value: string | number;
  sub?: string;
  trend?: "up" | "down" | "flat";
  highlight?: boolean;
  className?: string;
}

export function MetricWidget({ label, value, sub, trend, highlight, className }: MetricWidgetProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="data-label">{label}</span>
      <span
        className={cn(
          "metric-value text-2xl font-semibold tabular-nums",
          highlight ? "text-[#00d4ff]" : "text-slate-100"
        )}
      >
        {value}
        {trend === "up" && <span className="text-green-400 text-sm ml-1">↑</span>}
        {trend === "down" && <span className="text-red-400 text-sm ml-1">↓</span>}
      </span>
      {sub && <span className="text-[11px] text-slate-500">{sub}</span>}
    </div>
  );
}
