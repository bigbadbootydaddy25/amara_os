"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export interface IconFeatureItem {
  icon: ReactNode;
  label: string;
  body: string;
}

export interface IconFeatureRowProps {
  items: IconFeatureItem[];
  className?: string;
}

export function IconFeatureRow({ items, className }: IconFeatureRowProps) {
  return (
    <div
      className={cx(
        "grid grid-cols-1 divide-y divide-[var(--color-border)] border-y border-[var(--color-border)] sm:grid-cols-2 sm:divide-x sm:divide-y-0",
        items.length >= 4 && "lg:grid-cols-4",
        items.length === 3 && "lg:grid-cols-3",
        items.length >= 5 && "lg:grid-cols-5",
        className
      )}
    >
      {items.map((item, i) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: i * 0.06 }}
          className="flex flex-col gap-3 px-6 py-8"
        >
          <span className="text-[var(--color-gold)]" aria-hidden>
            {item.icon}
          </span>
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text)]">
            {item.label}
          </span>
          <p className="text-xs leading-relaxed text-[var(--color-text-muted)]">{item.body}</p>
        </motion.div>
      ))}
    </div>
  );
}
