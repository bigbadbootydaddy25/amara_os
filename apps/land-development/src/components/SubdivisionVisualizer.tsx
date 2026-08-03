"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cx } from "@aces/ui";
import {
  phases,
  layers,
  tractBoundary,
  mainRoad,
  crossRoads,
  lots,
  waterLines,
  sewerLines,
  stormLines,
  electricalCorridor,
  type LayerKey,
  type Lot,
} from "./subdivision-data";

const defaultToggles: Record<LayerKey, boolean> = {
  boundary: true,
  lots: true,
  roads: true,
  water: true,
  sewer: true,
  storm: true,
  electrical: true,
};

export function SubdivisionVisualizer() {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [view, setView] = useState<"aerial" | "3d">("aerial");
  const [toggles, setToggles] = useState(defaultToggles);
  const [hoveredLot, setHoveredLot] = useState<Lot | null>(null);
  const reduceMotion = useReducedMotion();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!playing) return;
    intervalRef.current = setInterval(() => {
      setPhaseIndex((prev) => {
        if (prev >= phases.length - 1) {
          setPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 3200);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing]);

  function togglePlay() {
    if (!playing && phaseIndex >= phases.length - 1) {
      setPhaseIndex(0);
    }
    setPlaying((p) => !p);
  }

  function goToPhase(index: number) {
    setPlaying(false);
    setPhaseIndex(index);
  }

  function toggleLayer(key: LayerKey) {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const layerVisible = (key: LayerKey) => {
    const def = layers.find((l) => l.key === key)!;
    return toggles[key] && phaseIndex >= def.availableFromPhase;
  };

  const paved = phaseIndex >= 3;
  const isBuildout = phaseIndex >= 4;
  const roadLines = [mainRoad, ...crossRoads];

  return (
    <section
      id="subdivision-visualizer"
      aria-labelledby="subdivision-heading"
      className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)] py-24"
    >
      <div className="mx-auto max-w-7xl px-6 md:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <span className="flex items-center justify-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
            <span aria-hidden className="h-px w-8 bg-[var(--color-gold)]" />
            How We Develop
          </span>
          <h2
            id="subdivision-heading"
            className="mt-4 font-[var(--font-display)] text-3xl text-[var(--color-text)] sm:text-4xl"
          >
            A fictional tract, from raw land to finished community.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-text-muted)]">
            This is an illustrative visualization of a hypothetical tract and does not
            represent an actual project.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr_260px]">
          <div className="order-1 flex flex-col gap-6">
            <ControlGroup title="Phase">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={togglePlay}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--color-gold)] text-[var(--color-gold)] transition-colors hover:bg-[var(--color-gold)] hover:text-[var(--color-bg)]"
                  aria-label={playing ? "Pause sequence" : "Play sequence"}
                >
                  {playing ? "❙❙" : "▶"}
                </button>
                <div className="flex flex-1 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => goToPhase(Math.max(0, phaseIndex - 1))}
                    disabled={phaseIndex === 0}
                    className="rounded px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-gold)] disabled:opacity-30"
                    aria-label="Previous phase"
                  >
                    &larr;
                  </button>
                  <button
                    type="button"
                    onClick={() => goToPhase(Math.min(phases.length - 1, phaseIndex + 1))}
                    disabled={phaseIndex === phases.length - 1}
                    className="rounded px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-gold)] disabled:opacity-30"
                    aria-label="Next phase"
                  >
                    &rarr;
                  </button>
                </div>
              </div>
              <ol className="mt-3 flex flex-col gap-1.5">
                {phases.map((phase, i) => (
                  <li key={phase.id}>
                    <button
                      type="button"
                      onClick={() => goToPhase(i)}
                      aria-pressed={i === phaseIndex}
                      className={cx(
                        "w-full rounded-md border px-3 py-2 text-left text-[11px] uppercase tracking-[0.08em] transition-colors duration-200",
                        i === phaseIndex
                          ? "border-[var(--color-gold)] bg-[var(--color-surface)] text-[var(--color-gold)]"
                          : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                      )}
                    >
                      {i + 1}. {phase.label}
                    </button>
                  </li>
                ))}
              </ol>
            </ControlGroup>

            <ControlGroup title="View">
              <div className="flex gap-2">
                {(["aerial", "3d"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setView(v)}
                    aria-pressed={view === v}
                    className={cx(
                      "flex-1 rounded-md border px-3 py-2 text-[11px] uppercase tracking-[0.1em] transition-colors duration-200",
                      view === v
                        ? "border-[var(--color-gold)] text-[var(--color-gold)]"
                        : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                    )}
                  >
                    {v === "aerial" ? "Aerial Plan" : "Angled 3D"}
                  </button>
                ))}
              </div>
            </ControlGroup>
          </div>

          <div className="order-3 lg:order-2">
            <div
              className="relative mx-auto overflow-visible"
              style={{ perspective: "1400px" }}
            >
              <motion.svg
                viewBox="0 0 100 100"
                className="aspect-[4/3] w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)]"
                animate={{
                  rotateX: view === "3d" ? 48 : 0,
                  scale: view === "3d" ? 0.94 : 1,
                }}
                transition={{ duration: reduceMotion ? 0 : 0.6, ease: "easeInOut" }}
                style={{ transformStyle: "preserve-3d" }}
              >
                <rect x={0} y={0} width={100} height={100} fill="var(--color-bg)" />
                {[...Array(5)].map((_, i) => (
                  <path
                    key={i}
                    d={`M ${2 + i * 3} 100 Q 50 ${20 + i * 6}, ${98 - i * 3} 100`}
                    fill="none"
                    stroke="var(--color-border)"
                    strokeWidth="0.3"
                    opacity={0.4}
                  />
                ))}

                {layerVisible("boundary") ? (
                  <motion.polygon
                    points={tractBoundary}
                    fill="none"
                    stroke="var(--color-gold)"
                    strokeWidth="0.6"
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ duration: reduceMotion ? 0 : 1.2 }}
                  />
                ) : null}

                {layerVisible("roads")
                  ? roadLines.map((line, i) => (
                      <motion.line
                        key={i}
                        x1={line.x1}
                        y1={line.y1}
                        x2={line.x2}
                        y2={line.y2}
                        stroke={paved ? "#c7c2b8" : "#7a756a"}
                        strokeWidth={paved ? 3 : 2}
                        strokeDasharray={paved ? undefined : "2 2"}
                        strokeLinecap="round"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: reduceMotion ? 0 : 0.9 }}
                      />
                    ))
                  : null}

                {layerVisible("water")
                  ? waterLines.map((line, i) => (
                      <motion.line
                        key={i}
                        x1={line.x1}
                        y1={line.y1}
                        x2={line.x2}
                        y2={line.y2}
                        stroke="#5fa8d3"
                        strokeWidth={0.6}
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: reduceMotion ? 0 : 1, delay: 0.1 }}
                      />
                    ))
                  : null}

                {layerVisible("sewer")
                  ? sewerLines.map((line, i) => (
                      <motion.line
                        key={i}
                        x1={line.x1}
                        y1={line.y1}
                        x2={line.x2}
                        y2={line.y2}
                        stroke="#b98b4e"
                        strokeWidth={0.6}
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: reduceMotion ? 0 : 1, delay: 0.25 }}
                      />
                    ))
                  : null}

                {layerVisible("storm")
                  ? stormLines.map((line, i) => (
                      <motion.line
                        key={i}
                        x1={line.x1}
                        y1={line.y1}
                        x2={line.x2}
                        y2={line.y2}
                        stroke="#5fd3c4"
                        strokeWidth={0.6}
                        strokeDasharray="1.5 1"
                        initial={{ pathLength: 0 }}
                        animate={{ pathLength: 1 }}
                        transition={{ duration: reduceMotion ? 0 : 1, delay: 0.4 }}
                      />
                    ))
                  : null}

                {layerVisible("electrical") ? (
                  <motion.polygon
                    points={electricalCorridor}
                    fill="none"
                    stroke="#e0c34a"
                    strokeWidth="0.5"
                    strokeDasharray="1 1.5"
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: 0.8 }}
                    transition={{ duration: reduceMotion ? 0 : 1.1, delay: 0.5 }}
                  />
                ) : null}

                {phaseIndex >= 2
                  ? lots.map((lot) => {
                      const built = isBuildout;
                      const showLines = layerVisible("lots");
                      return (
                        <g key={lot.id}>
                          {showLines ? (
                            <rect
                              x={lot.x}
                              y={lot.y}
                              width={lot.w}
                              height={lot.h}
                              fill={
                                built
                                  ? "rgba(91,125,94,0.35)"
                                  : "transparent"
                              }
                              stroke="var(--color-text-muted)"
                              strokeWidth={0.25}
                            />
                          ) : null}
                          {built && lot.hasStructure ? (
                            <motion.rect
                              x={lot.x + lot.w * 0.28}
                              y={lot.y + lot.h * 0.28}
                              width={lot.w * 0.44}
                              height={lot.h * 0.44}
                              fill="var(--color-gold)"
                              initial={{ scale: 0, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              transition={{ duration: reduceMotion ? 0 : 0.8, delay: 0.2 }}
                            />
                          ) : null}
                          {built && !lot.hasStructure
                            ? [0.25, 0.75].map((f, gi) => (
                                <motion.circle
                                  key={gi}
                                  cx={lot.x + lot.w * f}
                                  cy={lot.y + lot.h * 0.82}
                                  r={0.7}
                                  fill="#5b7d5e"
                                  initial={{ opacity: 0 }}
                                  animate={{ opacity: 0.9 }}
                                  transition={{ duration: reduceMotion ? 0 : 0.6, delay: 0.5 + gi * 0.1 }}
                                />
                              ))
                            : null}
                          {showLines ? (
                            <text
                              x={lot.x + lot.w / 2}
                              y={lot.y + lot.h / 2}
                              fontSize={2.4}
                              textAnchor="middle"
                              dominantBaseline="middle"
                              fill="var(--color-text-muted)"
                            >
                              {lot.id}
                            </text>
                          ) : null}
                          <rect
                            x={lot.x}
                            y={lot.y}
                            width={lot.w}
                            height={lot.h}
                            fill="transparent"
                            tabIndex={0}
                            role="button"
                            aria-label={`Lot ${lot.id}, status: ${lot.status}`}
                            onMouseEnter={() => setHoveredLot(lot)}
                            onMouseLeave={() => setHoveredLot(null)}
                            onFocus={() => setHoveredLot(lot)}
                            onBlur={() => setHoveredLot(null)}
                            style={{ cursor: "pointer", outline: "none" }}
                          />
                        </g>
                      );
                    })
                  : null}
              </motion.svg>
            </div>

            <p className="mt-4 text-center text-sm text-[var(--color-text-muted)]">
              {phases[phaseIndex].description}
            </p>
          </div>

          <div className="order-2 flex flex-col gap-6 lg:order-3">
            <ControlGroup title="Layers">
              <div className="flex flex-col gap-1.5">
                {layers.map((layer) => {
                  const available = phaseIndex >= layer.availableFromPhase;
                  return (
                    <button
                      key={layer.key}
                      type="button"
                      disabled={!available}
                      onClick={() => toggleLayer(layer.key)}
                      aria-pressed={toggles[layer.key] && available}
                      title={
                        available
                          ? undefined
                          : `Available from ${phases[layer.availableFromPhase].label}`
                      }
                      className={cx(
                        "flex items-center gap-2 rounded-md border px-3 py-2 text-left text-[11px] uppercase tracking-[0.06em] transition-colors duration-200",
                        !available && "cursor-not-allowed opacity-35",
                        available && toggles[layer.key]
                          ? "border-[var(--color-gold)] text-[var(--color-text)]"
                          : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                      )}
                    >
                      <span
                        aria-hidden
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{
                          backgroundColor:
                            available && toggles[layer.key] ? layer.color : "var(--color-border)",
                        }}
                      />
                      {layer.label}
                    </button>
                  );
                })}
              </div>
            </ControlGroup>

            <ControlGroup title="Lot Inspector">
              {hoveredLot ? (
                <div className="text-sm">
                  <p className="font-[var(--font-display)] text-base text-[var(--color-text)]">
                    Lot {hoveredLot.id}
                  </p>
                  <p className="mt-1 text-[var(--color-text-muted)]">
                    Status: {hoveredLot.status}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">
                  Hover or focus a lot on the map to see its fictional development status.
                </p>
              )}
            </ControlGroup>
          </div>
        </div>
      </div>
    </section>
  );
}

function ControlGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <span className="text-[10px] font-medium uppercase tracking-[0.25em] text-[var(--color-gold)]">
        {title}
      </span>
      <div className="mt-3">{children}</div>
    </div>
  );
}
