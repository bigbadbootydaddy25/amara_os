"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import type { StatItem } from "@aces/content";

export interface StatsStripProps {
  stats: StatItem[];
  icons?: ReactNode[];
}

export function StatsStrip({ stats, icons }: StatsStripProps) {
  return (
    <div className="border-y border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
      <div className="mx-auto grid max-w-7xl grid-cols-2 divide-x divide-[var(--color-border)] px-6 md:grid-cols-4 md:px-10">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: i * 0.08 }}
            className="flex flex-col gap-2 px-4 py-8 first:pl-0 sm:px-6"
          >
            {icons?.[i] ? (
              <span className="text-[var(--color-gold)]" aria-hidden>
                {icons[i]}
              </span>
            ) : null}
            <span className="font-[var(--font-display)] text-lg text-[var(--color-gold)] sm:text-xl">
              {stat.value}
            </span>
            <span className="text-[11px] uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
              {stat.label}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
