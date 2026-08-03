"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { getBrand } from "@aces/brand";
import type { DivisionProfile } from "@aces/content";
import { CTAButton } from "@aces/ui";

export interface CommandCenterProps {
  capitalName: string;
  divisions: DivisionProfile[];
}

const LINE_TARGETS = [16.67, 50, 83.33];

export function CommandCenter({ capitalName, divisions }: CommandCenterProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [userInteracted, setUserInteracted] = useState(false);
  const reduceMotion = useReducedMotion();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (reduceMotion || userInteracted) return;
    intervalRef.current = setInterval(() => {
      setActiveIndex((prev) => ((prev ?? -1) + 1) % divisions.length);
    }, 3600);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [reduceMotion, userInteracted, divisions.length]);

  function select(index: number) {
    setUserInteracted(true);
    if (intervalRef.current) clearInterval(intervalRef.current);
    setActiveIndex((prev) => (prev === index ? null : index));
  }

  const active = activeIndex !== null ? divisions[activeIndex] : null;
  const activeBrand = active ? getBrand(active.key) : null;

  return (
    <section
      id="platform"
      aria-labelledby="command-center-heading"
      className="relative scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)] py-24"
    >
      <div className="mx-auto max-w-7xl px-6 md:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <span className="flex items-center justify-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
            <span aria-hidden className="h-px w-8 bg-[var(--color-gold)]" />
            The Platform
          </span>
          <h2
            id="command-center-heading"
            className="mt-4 font-[var(--font-display)] text-3xl text-[var(--color-text)] sm:text-4xl"
          >
            One command center. Four companies, one platform.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-text-muted)]">
            Aces N 8s Capital directs strategy and capital across the platform. Select a
            division to see how it operates within the larger ecosystem.
          </p>
        </div>

        <div className="relative mt-16">
          <svg
            aria-hidden
            className="absolute inset-0 hidden h-full w-full md:block"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            {LINE_TARGETS.map((x, i) => {
              const isActive = activeIndex === i;
              return (
                <g key={i}>
                  <path
                    d={`M 50 20 Q ${(50 + x) / 2} 42, ${x} 58`}
                    fill="none"
                    stroke="var(--color-border)"
                    strokeWidth="0.3"
                  />
                  <motion.path
                    d={`M 50 20 Q ${(50 + x) / 2} 42, ${x} 58`}
                    fill="none"
                    stroke={isActive ? "var(--color-gold)" : "transparent"}
                    strokeWidth="0.4"
                    strokeDasharray="3 2"
                    initial={{ opacity: 0 }}
                    animate={{
                      opacity: isActive ? 1 : 0,
                      strokeDashoffset: isActive && !reduceMotion ? [0, -20] : 0,
                    }}
                    transition={{
                      opacity: { duration: 0.4 },
                      strokeDashoffset: { duration: 1.2, repeat: Infinity, ease: "linear" },
                    }}
                  />
                </g>
              );
            })}
          </svg>

          <div className="relative z-10 mx-auto flex w-fit flex-col items-center">
            <div className="flex flex-col items-center gap-2 rounded-2xl border border-[var(--color-gold)] bg-[var(--color-surface)] px-8 py-5 shadow-[0_0_40px_var(--glow)]">
              <span className="text-[10px] font-medium uppercase tracking-[0.25em] text-[var(--color-gold)]">
                Flagship Platform
              </span>
              <span className="font-[var(--font-display)] text-xl text-[var(--color-text)]">
                {capitalName}
              </span>
            </div>
          </div>

          <div className="relative z-10 mt-12 grid grid-cols-1 gap-5 sm:grid-cols-3">
            {divisions.map((division, i) => {
              const brand = getBrand(division.key);
              const isActive = activeIndex === i;
              return (
                <button
                  key={division.key}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => select(i)}
                  className="group flex flex-col items-center gap-3 rounded-xl border px-6 py-6 text-center transition-all duration-300"
                  style={{
                    borderColor: isActive ? brand.colors.gold : "var(--color-border)",
                    backgroundColor: isActive ? "var(--color-surface)" : "transparent",
                    boxShadow: isActive ? `0 0 30px ${brand.glow}` : "none",
                  }}
                >
                  <span
                    aria-hidden
                    className="h-2 w-2 rounded-full transition-colors duration-300"
                    style={{
                      backgroundColor: isActive ? brand.colors.gold : "var(--color-text-muted)",
                    }}
                  />
                  <span className="font-[var(--font-display)] text-base text-[var(--color-text)]">
                    {division.shortName}
                  </span>
                  <span className="text-[11px] uppercase tracking-[0.15em] text-[var(--color-text-muted)] group-hover:text-[var(--color-gold)]">
                    {isActive ? "Selected" : "Select"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <AnimatePresence mode="wait">
          {active && activeBrand ? (
            <motion.div
              key={active.key}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35 }}
              className="mx-auto mt-10 max-w-3xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center sm:p-10"
            >
              <span
                className="text-xs font-medium uppercase tracking-[0.25em]"
                style={{ color: activeBrand.colors.gold }}
              >
                {active.shortName}
              </span>
              <p className="mt-3 text-base leading-relaxed text-[var(--color-text)]">
                {active.purpose}
              </p>
              <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-muted)]">
                {active.role}
              </p>
              <div className="mt-6 flex justify-center">
                <CTAButton href={active.href} variant="primary" size="sm">
                  Visit {active.shortName}
                </CTAButton>
              </div>
            </motion.div>
          ) : (
            <p className="mx-auto mt-10 max-w-md text-center text-sm text-[var(--color-text-muted)]">
              Select a division above to see its role in the platform.
            </p>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
