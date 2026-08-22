"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import type { ParentPlatformLink } from "@aces/brand";
import { CTAButton } from "./CTAButton";
import { BrandMark } from "./BrandMark";
import { cx } from "../lib/cx";

export interface HeaderNavItem {
  label: string;
  href: string;
}

export interface HeaderProps {
  siteName: string;
  fullBrandName: string;
  nav?: HeaderNavItem[];
  secondaryLabel?: string;
  secondaryHref?: string;
  /** Renders a thin affiliation strip above the header for division sites. */
  parentPlatform?: ParentPlatformLink;
}

const defaultNav: HeaderNavItem[] = [
  { label: "About", href: "#about" },
  { label: "Platform", href: "#platform" },
  { label: "Contact", href: "#contact" },
];

export function Header({
  siteName,
  fullBrandName,
  nav = defaultNav,
  secondaryLabel,
  secondaryHref,
  parentPlatform,
}: HeaderProps) {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-[var(--color-bg)]/85 backdrop-blur-md">
      {parentPlatform ? (
        <div className="border-b border-white/10 bg-[var(--color-bg-elevated)]">
          <div className="mx-auto flex max-w-[1240px] items-center gap-2 px-6 py-1.5 text-[10px] uppercase tracking-[0.15em] text-[var(--color-text-muted)]">
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

      <div className="mx-auto flex h-[84px] max-w-[1240px] items-center justify-between px-6">
        <Link href="/" aria-label={siteName} onClick={() => setOpen(false)}>
          <BrandMark fullName={fullBrandName} size="sm" />
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <nav className="flex items-center gap-6">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm text-[#d8d0c1] transition-colors hover:text-[var(--color-gold)]"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          {secondaryLabel && secondaryHref ? (
            <Link
              href={secondaryHref}
              className="whitespace-nowrap text-xs font-medium uppercase tracking-[0.13em] text-[var(--color-gold)] transition-colors hover:text-[var(--color-gold-soft)]"
            >
              {secondaryLabel}
            </Link>
          ) : null}
        </div>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="flex h-10 w-10 flex-col items-center justify-center gap-1.5 md:hidden"
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
            className="overflow-hidden border-t border-white/10 md:hidden"
          >
            <nav className="flex flex-col gap-1 px-6 py-4">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="px-2 py-3 text-sm uppercase tracking-[0.2em] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-gold)]"
                >
                  {item.label}
                </Link>
              ))}
              {secondaryLabel && secondaryHref ? (
                <CTAButton
                  href={secondaryHref}
                  variant="secondary"
                  className="mt-3 justify-center"
                  onClick={() => setOpen(false)}
                >
                  {secondaryLabel}
                </CTAButton>
              ) : null}
            </nav>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
