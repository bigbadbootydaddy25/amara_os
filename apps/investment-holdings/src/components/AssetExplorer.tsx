"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cx } from "@aces/ui";
import { topics, assetCategories, pathwaySteps, type DiagramKind } from "./asset-explorer-data";

export function AssetExplorer() {
  const [activeKey, setActiveKey] = useState(topics[0].key);
  const [activeCategory, setActiveCategory] = useState<number | null>(null);
  const active = topics.find((t) => t.key === activeKey)!;

  return (
    <section
      id="asset-explorer"
      aria-labelledby="asset-explorer-heading"
      className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)] py-24"
    >
      <div className="mx-auto max-w-7xl px-6 md:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <span className="flex items-center justify-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
            <span aria-hidden className="h-px w-8 bg-[var(--color-gold)]" />
            Explore The Platform
          </span>
          <h2
            id="asset-explorer-heading"
            className="mt-4 font-[var(--font-display)] text-3xl text-[var(--color-text)] sm:text-4xl"
          >
            A restrained, institutional approach.
          </h2>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-10 lg:grid-cols-[280px_1fr]">
          <div className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
            {topics.map((topic) => (
              <button
                key={topic.key}
                type="button"
                onClick={() => setActiveKey(topic.key)}
                aria-pressed={activeKey === topic.key}
                className={cx(
                  "shrink-0 whitespace-nowrap rounded-md border px-4 py-3 text-left text-xs uppercase tracking-[0.1em] transition-colors duration-200 lg:whitespace-normal",
                  activeKey === topic.key
                    ? "border-[var(--color-gold)] bg-[var(--color-surface)] text-[var(--color-gold)]"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                )}
              >
                {topic.label}
              </button>
            ))}
          </div>

          <motion.div
            key={active.key}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
            className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 sm:p-10"
          >
            <p className="max-w-xl text-base leading-relaxed text-[var(--color-text)]">
              {active.body}
            </p>

            <div className="mt-8">
              {active.key === "assets" ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {assetCategories.map((cat, i) => (
                    <button
                      key={cat.label}
                      type="button"
                      onClick={() => setActiveCategory(activeCategory === i ? null : i)}
                      aria-pressed={activeCategory === i}
                      className={cx(
                        "rounded-lg border px-4 py-4 text-left transition-colors duration-200",
                        activeCategory === i
                          ? "border-[var(--color-gold)]"
                          : "border-[var(--color-border)] hover:border-[var(--color-gold)]"
                      )}
                    >
                      <span className="font-[var(--font-display)] text-sm text-[var(--color-text)]">
                        {cat.label}
                      </span>
                      {activeCategory === i ? (
                        <p className="mt-2 text-xs leading-relaxed text-[var(--color-text-muted)]">
                          {cat.body}
                        </p>
                      ) : null}
                    </button>
                  ))}
                </div>
              ) : active.key === "pathways" ? (
                <PathwayDiagram />
              ) : (
                <TopicDiagram kind={active.diagram} />
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function PathwayDiagram() {
  return (
    <div className="flex items-center justify-between gap-2">
      {pathwaySteps.map((step, i) => (
        <div key={step} className="flex flex-1 items-center">
          <div className="flex flex-col items-center gap-2 text-center">
            <span className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--color-gold)] text-xs text-[var(--color-gold)]">
              {i + 1}
            </span>
            <span className="text-[10px] uppercase tracking-[0.1em] text-[var(--color-text-muted)]">
              {step}
            </span>
          </div>
          {i < pathwaySteps.length - 1 ? (
            <span
              aria-hidden
              className="mx-2 h-px flex-1 bg-gradient-to-r from-[var(--color-gold)] to-[var(--color-border)]"
            />
          ) : null}
        </div>
      ))}
    </div>
  );
}

function TopicDiagram({ kind }: { kind: DiagramKind }) {
  const reduceMotion = useReducedMotion();

  return (
    <svg viewBox="0 0 100 60" className="h-40 w-full">
      {kind === "concentric" ? (
        <>
          {[24, 17, 10].map((r, i) => (
            <motion.circle
              key={r}
              cx={50}
              cy={30}
              r={r}
              fill="none"
              stroke="var(--color-gold)"
              strokeWidth={0.5}
              opacity={0.5}
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 0.5 }}
              transition={{ duration: reduceMotion ? 0 : 0.6, delay: i * 0.12 }}
            />
          ))}
          <circle cx={50} cy={30} r={3} fill="var(--color-gold)" />
        </>
      ) : null}

      {kind === "nodes" ? (
        <>
          <circle cx={50} cy={30} r={4} fill="var(--color-gold)" />
          {[
            [20, 12],
            [20, 48],
            [80, 12],
            [80, 48],
          ].map(([x, y], i) => (
            <g key={i}>
              <line x1={50} y1={30} x2={x} y2={y} stroke="var(--color-border)" strokeWidth={0.5} />
              <circle cx={x} cy={y} r={3} fill="var(--color-surface)" stroke="var(--color-gold)" strokeWidth={0.6} />
            </g>
          ))}
        </>
      ) : null}

      {kind === "radar" ? (
        <>
          <polygon
            points="50,6 88,30 72,54 28,54 12,30"
            fill="none"
            stroke="var(--color-border)"
            strokeWidth={0.5}
          />
          <motion.polygon
            points="50,16 72,32 63,48 37,48 28,32"
            fill="var(--glow)"
            stroke="var(--color-gold)"
            strokeWidth={0.6}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: reduceMotion ? 0 : 0.6 }}
          />
        </>
      ) : null}

      {kind === "ascend" ? (
        <>
          {[0, 1, 2, 3, 4].map((i) => {
            const fullHeight = (i + 1) * 8;
            return (
              <motion.rect
                key={i}
                x={14 + i * 16}
                width={8}
                fill="var(--color-gold)"
                opacity={0.25 + i * 0.15}
                initial={{ height: 0, y: 50 }}
                animate={{ height: fullHeight, y: 50 - fullHeight }}
                transition={{ duration: reduceMotion ? 0 : 0.5, delay: i * 0.08 }}
              />
            );
          })}
        </>
      ) : null}
    </svg>
  );
}
