"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import type { NavItem } from "@aces/content";
import type { ParentPlatformLink } from "@aces/brand";
import { CTAButton } from "./CTAButton";
import { BrandMark } from "./BrandMark";
import { cx } from "../lib/cx";

export interface HeaderProps {
  siteName: string;
  shortName: string;
  nav: NavItem[];
  ctaLabel?: string;
  ctaHref?: string;
  secondaryLabel?: string;
  secondaryHref?: string;
  /** Renders a thin affiliation strip above the header for division sites. */
  parentPlatform?: ParentPlatformLink;
  /** Color for the brand mark's subtitle line; defaults to the site accent. */
  brandSubtitleColorVar?: string;
}

export function Header({
  siteName,
  shortName,
  nav,
  ctaLabel,
  ctaHref,
  secondaryLabel,
  secondaryHref,
  parentPlatform,
  brandSubtitleColorVar,
}: HeaderProps) {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 backdrop-blur-md">
      {parentPlatform ? (
        <div className="border-b border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
          <div className="mx-auto flex max-w-7xl items-center gap-2 px-6 py-1.5 text-[10px] uppercase tracking-[0.15em] text-[var(--color-text-muted)] md:px-8">
            <span>{parentPlatform.label}</span>
            <a
              href={parentPlatform.href}
              className="font-medium text-[var(--color-gold)] transition-colors hover:text-[var(--color-gold-soft)]"
            >
              {parentPlatform.name}
              <span aria-hidden> &rarr;</span>
            </a>
          </div>
        </div>
      ) : null}
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-6 py-4 md:px-7">
        <Link
          href="/"
          aria-label={siteName}
          className="flex shrink-0 items-center whitespace-nowrap"
          onClick={() => setOpen(false)}
        >
          <BrandMark shortName={shortName} subtitleColorVar={brandSubtitleColorVar} size="sm" />
        </Link>

        <nav className="hidden min-w-0 items-center gap-3 overflow-x-auto xl:flex xl:gap-5">
          {nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="whitespace-nowrap text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--color-text-muted)] transition-colors duration-200 hover:text-[var(--color-gold)] xl:text-xs xl:tracking-[0.15em]"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden shrink-0 items-center gap-2.5 xl:flex xl:gap-3">
          {secondaryLabel && secondaryHref ? (
            <Link
              href={secondaryHref}
              className="whitespace-nowrap text-[11px] font-medium uppercase tracking-[0.13em] text-[var(--color-gold)] transition-colors hover:text-[var(--color-gold-soft)] xl:text-xs"
            >
              {secondaryLabel}
            </Link>
          ) : null}
          {ctaLabel && ctaHref ? (
            <CTAButton href={ctaHref} variant="primary" size="sm" className="whitespace-nowrap">
              {ctaLabel}
            </CTAButton>
          ) : null}
        </div>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="flex h-10 w-10 flex-col items-center justify-center gap-1.5 xl:hidden"
        >
          <span
            aria-hidden
            className={cx(
              "h-px w-6 bg-[var(--color-gold)] transition-transform duration-300",
              open && "translate-y-[7px] rotate-45"
            )}
          />
          <span
            aria-hidden
            className={cx(
              "h-px w-6 bg-[var(--color-gold)] transition-opacity duration-300",
              open && "opacity-0"
            )}
          />
          <span
            aria-hidden
            className={cx(
              "h-px w-6 bg-[var(--color-gold)] transition-transform duration-300",
              open && "-translate-y-[7px] -rotate-45"
            )}
          />
        </button>
      </div>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden border-t border-[var(--color-border)] xl:hidden"
          >
            <nav className="flex flex-col gap-1 px-6 py-4">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="rounded-md px-2 py-3 text-sm uppercase tracking-[0.2em] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-gold)]"
                >
                  {item.label}
                </Link>
              ))}
              <div className="mt-3 flex flex-col gap-3">
                {secondaryLabel && secondaryHref ? (
                  <CTAButton href={secondaryHref} variant="secondary" className="justify-center">
                    {secondaryLabel}
                  </CTAButton>
                ) : null}
                {ctaLabel && ctaHref ? (
                  <CTAButton href={ctaHref} variant="primary" className="justify-center">
                    {ctaLabel}
                  </CTAButton>
                ) : null}
              </div>
            </nav>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
