"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";

export interface DiagonalImageItem {
  label: string;
  body: string;
  icon: ReactNode;
}

export interface DiagonalImageGridProps {
  items: DiagonalImageItem[];
}

const SKEW = 6;

export function DiagonalImageGrid({ items }: DiagonalImageGridProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item, i) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, delay: i * 0.08 }}
          className="group relative flex h-72 flex-col justify-end overflow-hidden border border-[var(--color-border)] p-6"
          style={{
            clipPath: `polygon(${SKEW}% 0%, 100% 0%, ${100 - SKEW}% 100%, 0% 100%)`,
            background:
              "linear-gradient(155deg, var(--color-surface) 0%, var(--color-bg-elevated) 55%, var(--color-bg) 100%)",
          }}
        >
          <span
            aria-hidden
            className="pointer-events-none absolute -right-2 -top-2 scale-[5] text-[var(--color-gold)] opacity-[0.08] transition-opacity duration-300 group-hover:opacity-[0.14]"
          >
            {item.icon}
          </span>
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[var(--color-bg)] via-transparent to-transparent"
          />
          <div className="relative z-10 flex flex-col gap-2">
            <span className="text-[var(--color-gold)]">{item.icon}</span>
            <h3 className="font-[var(--font-display)] text-lg text-[var(--color-text)]">
              {item.label}
            </h3>
            <p className="text-xs leading-relaxed text-[var(--color-text-muted)]">{item.body}</p>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
