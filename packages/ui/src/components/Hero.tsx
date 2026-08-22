"use client";

import { motion } from "framer-motion";
import type { HeroContent } from "@aces/content";
import { CTAButton } from "./CTAButton";
import { AnimatedBackground, type BackgroundVariant } from "./AnimatedBackground";

export interface HeroProps {
  hero: HeroContent;
  eyebrow: string;
  backgroundVariant?: BackgroundVariant;
}

export function Hero({ hero, eyebrow, backgroundVariant = "aurora" }: HeroProps) {
  return (
    <section className="border-b border-white/10">
      <div className="mx-auto grid max-w-[1240px] grid-cols-1 items-center gap-10 px-6 py-16 md:min-h-[76vh] md:grid-cols-[1.05fr_0.95fr] md:gap-12 md:py-20">
        <div>
          <motion.span
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="block text-xs uppercase tracking-[0.22em] text-[var(--color-gold)]"
          >
            {eyebrow}
          </motion.span>

          <h1 className="mt-4 font-[var(--font-display)] text-[clamp(2.5rem,7vw,5.75rem)] font-bold leading-[0.95] text-[var(--color-text)]">
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
            className="mt-5 max-w-xl text-lg leading-relaxed text-[#c9c1b3]"
          >
            {hero.body}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.65 }}
            className="mt-6 flex flex-wrap items-center gap-4"
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
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="relative min-h-[340px] overflow-hidden border border-[var(--glow)] bg-[#09090b] md:min-h-[520px]"
        >
          <AnimatedBackground variant={backgroundVariant} className="opacity-90" />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-6 border border-[var(--color-gold)]/35"
          />
        </motion.div>
      </div>
    </section>
  );
}
