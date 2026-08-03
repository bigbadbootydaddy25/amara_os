"use client";

import { motion } from "framer-motion";
import { cx } from "../lib/cx";

export interface InfoCardItem {
  title: string;
  body: string;
}

export interface InfoCardsProps {
  items: InfoCardItem[];
  columns?: 2 | 3 | 4;
  className?: string;
}

export function InfoCards({ items, columns = 4, className }: InfoCardsProps) {
  return (
    <div
      className={cx(
        "grid grid-cols-1 gap-4 sm:grid-cols-2",
        columns === 3 && "lg:grid-cols-3",
        columns === 4 && "lg:grid-cols-4",
        className
      )}
    >
      {items.map((item, i) => (
        <motion.div
          key={item.title}
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: i * 0.06 }}
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-elevated)] p-6 transition-colors duration-300 hover:border-[var(--color-gold)]"
        >
          <h4 className="font-[var(--font-display)] text-lg text-[var(--color-text)]">
            {item.title}
          </h4>
          <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-muted)]">
            {item.body}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
