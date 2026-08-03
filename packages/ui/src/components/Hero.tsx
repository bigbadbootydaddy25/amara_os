"use client";

import { motion } from "framer-motion";
import type { HeroContent } from "@aces/content";
import { CTAButton } from "./CTAButton";
import { AnimatedBackground, type BackgroundVariant } from "./AnimatedBackground";

export interface HeroProps {
  hero: HeroContent;
  backgroundVariant?: BackgroundVariant;
}

export function Hero({ hero, backgroundVariant = "aurora" }: HeroProps) {
  return (
    <section className="relative flex min-h-[92vh] items-center overflow-hidden border-b border-[var(--color-border)]">
      <AnimatedBackground variant={backgroundVariant} />

      <div className="relative z-10 mx-auto flex w-full max-w-7xl flex-col items-start px-6 py-32 md:px-10">
        {hero.eyebrow ? (
          <motion.span
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mb-6 flex items-center gap-3 text-xs font-medium uppercase tracking-[0.35em] text-[var(--color-gold)]"
          >
            <span aria-hidden className="h-px w-10 bg-[var(--color-gold)]" />
            {hero.eyebrow}
          </motion.span>
        ) : null}

        <h1 className="font-[var(--font-display)] text-4xl font-normal leading-[1.05] text-[var(--color-text)] sm:text-6xl md:text-7xl">
          {hero.headline.map((line, i) => (
            <motion.span
              key={line}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.1 + i * 0.12 }}
              className="block"
            >
              {line}
            </motion.span>
          ))}
        </h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.5 }}
          className="mt-8 max-w-xl text-base leading-relaxed text-[var(--color-text-muted)] sm:text-lg"
        >
          {hero.body}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.65 }}
          className="mt-10 flex flex-wrap items-center gap-4"
        >
          <CTAButton href={hero.ctaHref} variant="primary">
            {hero.ctaLabel}
          </CTAButton>
          {hero.secondaryLabel && hero.secondaryHref ? (
            <CTAButton href={hero.secondaryHref} variant="secondary">
              {hero.secondaryLabel}
            </CTAButton>
          ) : null}
        </motion.div>
      </div>

      <motion.div
        aria-hidden
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1, delay: 1 }}
        className="absolute bottom-8 left-1/2 z-10 hidden -translate-x-1/2 flex-col items-center gap-2 sm:flex"
      >
        <span className="text-[10px] uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          Scroll
        </span>
        <span className="h-10 w-px bg-gradient-to-b from-[var(--color-gold)] to-transparent" />
      </motion.div>
    </section>
  );
}
