"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cx } from "../lib/cx";

export type BackgroundVariant = "skyline" | "map-grid" | "aurora" | "blueprint";

export interface AnimatedBackgroundProps {
  variant?: BackgroundVariant;
  className?: string;
}

export function AnimatedBackground({
  variant = "aurora",
  className,
}: AnimatedBackgroundProps) {
  const shouldReduceMotion = useReducedMotion();

  return (
    <div
      aria-hidden
      className={cx(
        "pointer-events-none absolute inset-0 overflow-hidden",
        className
      )}
    >
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% -10%, var(--glow), transparent 70%)",
        }}
      />

      {variant === "skyline" ? <SkylineLayer reduceMotion={!!shouldReduceMotion} /> : null}
      {variant === "map-grid" ? <MapGridLayer reduceMotion={!!shouldReduceMotion} /> : null}
      {variant === "aurora" ? <AuroraLayer reduceMotion={!!shouldReduceMotion} /> : null}
      {variant === "blueprint" ? <BlueprintLayer reduceMotion={!!shouldReduceMotion} /> : null}

      <CrestWatermark />

      <div
        className="absolute inset-0 opacity-[0.05]"
        style={{
          backgroundImage:
            "linear-gradient(var(--color-border) 1px, transparent 1px), linear-gradient(90deg, var(--color-border) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />

      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(to bottom, transparent 0%, var(--color-bg) 96%)",
        }}
      />
    </div>
  );
}

function CrestWatermark() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 200 260"
      className="absolute -right-10 bottom-0 hidden h-[110%] w-auto text-[var(--color-gold)] opacity-[0.05] sm:block md:opacity-[0.06]"
    >
      <path
        d="M30 40 L45 20 L60 34 L100 5 L140 34 L155 20 L170 40 L162 100 C162 170 130 220 100 235 C70 220 38 170 38 100 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="100" cy="5" r="5" fill="currentColor" />
      <circle cx="45" cy="20" r="3.6" fill="currentColor" />
      <circle cx="155" cy="20" r="3.6" fill="currentColor" />
      <path
        d="M100 70c-18 20-42 38-42 60a28 28 0 0 0 46 21c-4 10-8 17-15 23h22c-7-6-11-13-15-23a28 28 0 0 0 46-21c0-22-24-40-42-60Z"
        fill="currentColor"
        opacity={0.9}
      />
      <text
        x="100"
        y="200"
        textAnchor="middle"
        fontSize="34"
        fontFamily="serif"
        fill="currentColor"
      >
        8
      </text>
    </svg>
  );
}

function SkylineLayer({ reduceMotion }: { reduceMotion: boolean }) {
  const bars = [18, 34, 22, 48, 30, 56, 26, 42, 20, 38, 24, 50];
  return (
    <svg
      className="absolute inset-x-0 bottom-0 h-1/2 w-full opacity-40"
      viewBox="0 0 600 120"
      preserveAspectRatio="none"
    >
      {bars.map((h, i) => (
        <motion.rect
          key={i}
          x={i * 50 + 4}
          width={34}
          y={120 - h}
          height={h}
          fill="var(--color-gold)"
          initial={{ opacity: 0.15 }}
          animate={reduceMotion ? undefined : { opacity: [0.15, 0.35, 0.15] }}
          transition={{
            duration: 6 + (i % 4),
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * 0.2,
          }}
        />
      ))}
    </svg>
  );
}

function MapGridLayer({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <motion.div
      className="absolute inset-0 opacity-30"
      style={{
        backgroundImage:
          "linear-gradient(var(--color-gold) 1px, transparent 1px), linear-gradient(90deg, var(--color-gold) 1px, transparent 1px)",
        backgroundSize: "120px 120px",
      }}
      initial={{ opacity: 0.12 }}
      animate={reduceMotion ? undefined : { opacity: [0.12, 0.22, 0.12] }}
      transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
    />
  );
}

function AuroraLayer({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <motion.div
      className="absolute -inset-1/4"
      style={{
        background:
          "conic-gradient(from 90deg at 50% 50%, var(--glow), transparent 30%, transparent 70%, var(--glow))",
        filter: "blur(60px)",
      }}
      initial={{ rotate: 0, opacity: 0.5 }}
      animate={reduceMotion ? undefined : { rotate: 360 }}
      transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
    />
  );
}

function BlueprintLayer({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <>
      <motion.div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            "linear-gradient(var(--color-accent-soft) 1px, transparent 1px), linear-gradient(90deg, var(--color-accent-soft) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      {[...Array(4)].map((_, i) => (
        <motion.span
          key={i}
          className="absolute h-2 w-2 rounded-full border border-[var(--color-gold)]"
          style={{
            left: `${18 + i * 20}%`,
            top: `${28 + (i % 3) * 18}%`,
          }}
          initial={{ opacity: 0.3, scale: 1 }}
          animate={
            reduceMotion
              ? undefined
              : { opacity: [0.3, 0.9, 0.3], scale: [1, 1.6, 1] }
          }
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
            delay: i * 0.6,
          }}
        />
      ))}
    </>
  );
}
