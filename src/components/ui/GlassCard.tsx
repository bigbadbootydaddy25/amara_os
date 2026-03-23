"use client";

import { cn } from "@/lib/utils";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  glow?: "signal" | "deal" | "amber" | "none";
  onClick?: () => void;
}

export function GlassCard({ children, className, glow = "none", onClick }: GlassCardProps) {
  const glowClass = {
    signal: "border-[rgba(0,212,255,0.12)] shadow-[0_0_24px_rgba(0,212,255,0.08)]",
    deal: "border-[rgba(16,185,129,0.18)] shadow-[0_0_24px_rgba(16,185,129,0.08)]",
    amber: "border-[rgba(245,158,11,0.18)] shadow-[0_0_24px_rgba(245,158,11,0.08)]",
    none: "border-[rgba(255,255,255,0.04)]",
  }[glow];

  return (
    <div
      onClick={onClick}
      className={cn(
        "glass-panel border rounded-lg transition-all duration-200",
        glowClass,
        onClick && "cursor-pointer hover:border-[rgba(0,212,255,0.2)] hover:shadow-[0_0_32px_rgba(0,212,255,0.1)]",
        className
      )}
    >
      {children}
    </div>
  );
}
