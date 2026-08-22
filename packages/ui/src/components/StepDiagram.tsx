"use client";

import { useState, type ReactNode } from "react";
import { cx } from "../lib/cx";

export interface StepDiagramStep {
  label: string;
}

export interface StepDiagramProps {
  steps: StepDiagramStep[];
  children: (activeIndex: number) => ReactNode;
}

export function StepDiagram({ steps, children }: StepDiagramProps) {
  const [active, setActive] = useState(0);

  return (
    <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
      <div className="grid grid-cols-2 gap-2 border border-white/10 bg-[#09090b] p-4 sm:grid-cols-1">
        {steps.map((step, i) => (
          <button
            key={step.label}
            type="button"
            onClick={() => setActive(i)}
            aria-pressed={i === active}
            className={cx(
              "border px-3 py-3 text-left text-sm transition-colors duration-200",
              i === active
                ? "border-[var(--color-gold)] bg-[color-mix(in_srgb,var(--color-gold)_9%,transparent)] text-white"
                : "border-white/10 text-[#d8d0c1] hover:border-[var(--color-gold)] hover:text-white"
            )}
          >
            {step.label}
          </button>
        ))}
      </div>

      <div className="relative min-h-[380px] overflow-hidden border border-white/10 bg-[#08090a] sm:min-h-[440px]">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background: "radial-gradient(circle at center, var(--glow), transparent 40%)",
          }}
        />
        {children(active)}
        <div className="absolute bottom-4 left-4 z-10 border border-[var(--color-gold)] bg-[var(--color-bg)]/90 px-4 py-2.5 text-sm text-white">
          {steps[active].label}
        </div>
      </div>
    </div>
  );
}

export interface DiagramLayerProps {
  layer: number;
  activeIndex: number;
  children: ReactNode;
  className?: string;
}

/**
 * Wraps a layer of a step diagram's SVG content. Reveals with opacity +
 * translateY once `activeIndex` reaches `layer`; instant when the layer is
 * already visible on mount, respecting reduced-motion via a plain CSS
 * transition (globally shortened under prefers-reduced-motion).
 */
export function DiagramLayer({ layer, activeIndex, children, className }: DiagramLayerProps) {
  const visible = activeIndex >= layer;
  return (
    <g
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
        transition: "opacity 0.4s ease, transform 0.4s ease",
      }}
    >
      {children}
    </g>
  );
}
