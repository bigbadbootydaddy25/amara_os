"use client";

import { cn } from "@/lib/utils";

type PulseColor = "green" | "amber" | "red" | "signal" | "gray";

interface StatusPulseProps {
  color?: PulseColor;
  label?: string;
  className?: string;
}

const colorMap: Record<PulseColor, string> = {
  green: "bg-green-400",
  amber: "bg-amber-400",
  red: "bg-red-400",
  signal: "bg-[#00d4ff]",
  gray: "bg-slate-600",
};

export function StatusPulse({ color = "signal", label, className }: StatusPulseProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative flex h-2 w-2">
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-ping rounded-full opacity-50",
            colorMap[color]
          )}
        />
        <span
          className={cn(
            "relative inline-flex h-2 w-2 rounded-full",
            colorMap[color]
          )}
        />
      </div>
      {label && (
        <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400">
          {label}
        </span>
      )}
    </div>
  );
}
