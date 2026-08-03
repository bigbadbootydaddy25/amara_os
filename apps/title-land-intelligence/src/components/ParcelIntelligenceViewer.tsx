"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cx } from "@aces/ui";
import {
  parcelBoundary,
  surfaceOwnership,
  mineralOwnership,
  easements,
  rightOfWay,
  encumbrance,
  gisPins,
  titleChain,
  flags,
  layers,
  type LayerKey,
  type FlagMarker,
} from "./title-data";

const defaultToggles: Record<LayerKey, boolean> = {
  boundary: true,
  surface: true,
  mineral: false,
  easements: false,
  row: false,
  encumbrances: false,
  gis: false,
};

export function ParcelIntelligenceViewer() {
  const [toggles, setToggles] = useState(defaultToggles);
  const [selectedFlag, setSelectedFlag] = useState<FlagMarker | null>(null);
  const reduceMotion = useReducedMotion();

  function toggleLayer(key: LayerKey) {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <section
      id="parcel-intelligence"
      aria-labelledby="parcel-intelligence-heading"
      className="scroll-mt-24 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)] py-24"
    >
      <div className="mx-auto max-w-7xl px-6 md:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <span className="flex items-center justify-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
            <span aria-hidden className="h-px w-8 bg-[var(--color-gold)]" />
            Land Intelligence
          </span>
          <h2
            id="parcel-intelligence-heading"
            className="mt-4 font-[var(--font-display)] text-3xl text-[var(--color-text)] sm:text-4xl"
          >
            A fictional parcel, layered with title intelligence.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-[var(--color-text-muted)]">
            This is an illustrative visualization using a fictional parcel. No real client
            data, owner names, or project locations are represented.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr_280px]">
          <div className="order-1">
            <ControlGroup title="Layers">
              <div className="flex flex-col gap-1.5">
                {layers.map((layer) => (
                  <button
                    key={layer.key}
                    type="button"
                    onClick={() => toggleLayer(layer.key)}
                    aria-pressed={toggles[layer.key]}
                    className={cx(
                      "flex items-center gap-2 rounded-md border px-3 py-2 text-left text-[11px] uppercase tracking-[0.06em] transition-colors duration-200",
                      toggles[layer.key]
                        ? "border-[var(--color-gold)] text-[var(--color-text)]"
                        : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                    )}
                  >
                    <span
                      aria-hidden
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{
                        backgroundColor: toggles[layer.key] ? layer.color : "var(--color-border)",
                      }}
                    />
                    {layer.label}
                  </button>
                ))}
              </div>
            </ControlGroup>
          </div>

          <div className="order-3 lg:order-2">
            <svg
              viewBox="0 0 100 100"
              className="aspect-square w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)]"
            >
              {toggles.gis ? (
                <g opacity={0.5}>
                  <defs>
                    <pattern id="gis-grid" width="8" height="8" patternUnits="userSpaceOnUse">
                      <path d="M 8 0 L 0 0 0 8" fill="none" stroke="#5fd3c4" strokeWidth="0.2" />
                    </pattern>
                  </defs>
                  <rect x={0} y={0} width={100} height={100} fill="url(#gis-grid)" />
                  {gisPins.map((pin, i) => (
                    <motion.circle
                      key={i}
                      cx={pin.x}
                      cy={pin.y}
                      r={1.2}
                      fill="#5fd3c4"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 0.9 }}
                      transition={{ duration: reduceMotion ? 0 : 0.4, delay: i * 0.08 }}
                    />
                  ))}
                </g>
              ) : null}

              {toggles.surface
                ? surfaceOwnership.map((block) => (
                    <polygon
                      key={block.id}
                      points={block.points}
                      fill={block.color}
                      opacity={0.28}
                      stroke={block.color}
                      strokeWidth={0.3}
                    />
                  ))
                : null}

              {toggles.mineral ? (
                <motion.polygon
                  points={mineralOwnership.points}
                  fill="none"
                  stroke="#8b93a3"
                  strokeWidth={0.6}
                  strokeDasharray="1 1"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.9 }}
                  transition={{ duration: reduceMotion ? 0 : 0.5 }}
                />
              ) : null}

              {toggles.row ? (
                <polygon points={rightOfWay.points} fill="#2c567e" opacity={0.3} />
              ) : null}

              {toggles.encumbrances ? (
                <polygon
                  points={encumbrance.points}
                  fill="#a8283a"
                  opacity={0.3}
                  stroke="#a8283a"
                  strokeWidth={0.4}
                />
              ) : null}

              {toggles.easements
                ? easements.map((line, i) => (
                    <motion.line
                      key={i}
                      x1={line.x1}
                      y1={line.y1}
                      x2={line.x2}
                      y2={line.y2}
                      stroke="#dcc389"
                      strokeWidth={0.4}
                      strokeDasharray="1.5 1"
                      initial={{ pathLength: 0 }}
                      animate={{ pathLength: 1 }}
                      transition={{ duration: reduceMotion ? 0 : 0.7, delay: i * 0.1 }}
                    />
                  ))
                : null}

              {toggles.boundary ? (
                <motion.polygon
                  points={parcelBoundary}
                  fill="none"
                  stroke="var(--color-gold)"
                  strokeWidth={0.6}
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: reduceMotion ? 0 : 1 }}
                />
              ) : null}

              {flags.map((flag) => (
                <g key={flag.id}>
                  <circle
                    cx={flag.x}
                    cy={flag.y}
                    r={2.4}
                    fill={flag.kind === "gap" ? "#a8283a" : "#b99c5e"}
                    opacity={selectedFlag?.id === flag.id ? 1 : 0.85}
                    stroke="var(--color-bg)"
                    strokeWidth={0.4}
                  />
                  <text
                    x={flag.x}
                    y={flag.y + 0.9}
                    fontSize={2.6}
                    textAnchor="middle"
                    fill="var(--color-bg)"
                    fontWeight="bold"
                  >
                    !
                  </text>
                  <rect
                    x={flag.x - 3}
                    y={flag.y - 3}
                    width={6}
                    height={6}
                    fill="transparent"
                    tabIndex={0}
                    role="button"
                    aria-label={flag.label}
                    onClick={() => setSelectedFlag(flag)}
                    onFocus={() => setSelectedFlag(flag)}
                    style={{ cursor: "pointer", outline: "none" }}
                  />
                </g>
              ))}
            </svg>
          </div>

          <div className="order-2 flex flex-col gap-6 lg:order-3">
            <ControlGroup title="Selected Item">
              {selectedFlag ? (
                <p className="text-sm leading-relaxed text-[var(--color-text)]">
                  {selectedFlag.label}
                </p>
              ) : (
                <p className="text-sm text-[var(--color-text-muted)]">
                  Select a flagged marker on the map for details.
                </p>
              )}
            </ControlGroup>

            <ControlGroup title="Title Chain (Fictional)">
              <ol className="flex flex-col gap-3">
                {titleChain.map((instrument, i) => (
                  <motion.li
                    key={instrument.year}
                    initial={{ opacity: 0, x: -8 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: reduceMotion ? 0 : 0.4, delay: i * 0.06 }}
                    className="flex items-baseline gap-3 border-l border-[var(--color-border)] pl-3"
                  >
                    <span className="text-xs font-medium text-[var(--color-gold)]">
                      {instrument.year}
                    </span>
                    <span className="text-xs text-[var(--color-text-muted)]">
                      {instrument.label}
                    </span>
                  </motion.li>
                ))}
              </ol>
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
