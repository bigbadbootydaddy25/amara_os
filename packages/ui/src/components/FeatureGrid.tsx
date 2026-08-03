"use client";

import { motion } from "framer-motion";
import type { SectionContent } from "@aces/content";
import { cx } from "../lib/cx";

export interface FeatureGridProps {
  sections: SectionContent[];
  columns?: 2 | 3;
  className?: string;
}

export function FeatureGrid({ sections, columns = 3, className }: FeatureGridProps) {
  return (
    <div
      className={cx(
        "grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-border)] sm:grid-cols-2",
        columns === 3 && "lg:grid-cols-3",
        className
      )}
    >
      {sections.map((section, i) => (
        <motion.div
          key={section.id}
          id={section.id}
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, delay: (i % 3) * 0.08 }}
          className="group relative flex scroll-mt-24 flex-col gap-4 bg-[var(--color-bg-elevated)] p-8 transition-colors duration-300 hover:bg-[var(--color-surface)]"
        >
          <span className="text-xs font-medium tracking-[0.3em] text-[var(--color-gold)]">
            {String(i + 1).padStart(2, "0")}
          </span>
          <h3 className="font-[var(--font-display)] text-xl text-[var(--color-text)] sm:text-2xl">
            {section.title}
          </h3>
          <p className="text-sm leading-relaxed text-[var(--color-text-muted)]">
            {section.body}
          </p>
          {section.bullets ? (
            <ul className="mt-2 flex flex-col gap-2">
              {section.bullets.map((b) => (
                <li
                  key={b}
                  className="flex items-start gap-2 text-sm text-[var(--color-text-muted)]"
                >
                  <span
                    aria-hidden
                    className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[var(--color-gold)]"
                  />
                  {b}
                </li>
              ))}
            </ul>
          ) : null}
          <span
            aria-hidden
            className="absolute inset-x-0 bottom-0 h-px scale-x-0 bg-[var(--color-gold)] transition-transform duration-300 group-hover:scale-x-100"
          />
        </motion.div>
      ))}
    </div>
  );
}
