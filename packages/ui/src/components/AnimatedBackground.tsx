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
