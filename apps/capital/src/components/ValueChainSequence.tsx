"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import type { ValueChainStage } from "@aces/content";

export interface ValueChainSequenceProps {
  stages: ValueChainStage[];
}

export function ValueChainSequence({ stages }: ValueChainSequenceProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [userInteracted, setUserInteracted] = useState(false);
  const reduceMotion = useReducedMotion();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (reduceMotion || userInteracted) return;
    intervalRef.current = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % stages.length);
    }, 2800);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [reduceMotion, userInteracted, stages.length]);

  function select(index: number) {
    setUserInteracted(true);
    if (intervalRef.current) clearInterval(intervalRef.current);
    setActiveIndex(index);
  }

  const progress = stages.length > 1 ? activeIndex / (stages.length - 1) : 0;

  return (
    <section
      aria-labelledby="value-chain-heading"
      className="border-t border-[var(--color-border)] py-24"
    >
      <div className="mx-auto max-w-7xl px-6 md:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <span className="flex items-center justify-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
            <span aria-hidden className="h-px w-8 bg-[var(--color-gold)]" />
            End-to-End Value Creation
          </span>
          <h2
            id="value-chain-heading"
            className="mt-4 font-[var(--font-display)] text-3xl text-[var(--color-text)] sm:text-4xl"
          >
            From capital alignment to finished value.
          </h2>
        </div>

        <div className="mt-16 overflow-x-auto">
          <div className="relative mx-auto min-w-[720px] max-w-5xl px-2">
            <div className="absolute left-0 right-0 top-3 h-px bg-[var(--color-border)]" />
            <motion.div
              className="absolute left-0 top-3 h-px bg-[var(--color-gold)]"
              initial={false}
              animate={{ width: `${progress * 100}%` }}
              transition={{ duration: 0.5 }}
            />
            <ol className="relative flex justify-between">
              {stages.map((stage, i) => {
                const isActive = i === activeIndex;
                const isDone = i < activeIndex;
                return (
                  <li key={stage.id} className="flex flex-1 flex-col items-center">
                    <button
                      type="button"
                      onClick={() => select(i)}
                      aria-pressed={isActive}
                      aria-label={stage.label}
                      className="relative flex h-6 w-6 items-center justify-center rounded-full border transition-colors duration-300"
                      style={{
                        borderColor:
                          isActive || isDone ? "var(--color-gold)" : "var(--color-border)",
                        backgroundColor: isActive
                          ? "var(--color-gold)"
                          : isDone
                            ? "var(--color-surface)"
                            : "var(--color-bg-elevated)",
                      }}
                    >
                      {isActive ? (
                        <span
                          aria-hidden
                          className="absolute inset-0 rounded-full"
                          style={{ boxShadow: "0 0 16px var(--glow)" }}
                        />
                      ) : null}
                    </button>
                    <span
                      className="mt-3 max-w-[110px] text-center text-[10px] font-medium uppercase leading-tight tracking-[0.1em] transition-colors duration-300"
                      style={{
                        color: isActive ? "var(--color-gold)" : "var(--color-text-muted)",
                      }}
                    >
                      {stage.label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>

        <motion.div
          key={stages[activeIndex].id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35 }}
          className="mx-auto mt-10 max-w-xl text-center"
        >
          <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">
            {stages[activeIndex].detail}
          </p>
        </motion.div>
      </div>
    </section>
  );
}
