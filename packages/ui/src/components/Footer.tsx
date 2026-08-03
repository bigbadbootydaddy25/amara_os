import Link from "next/link";
import type { NavItem } from "@aces/content";

export interface FooterProps {
  siteName: string;
  tagline?: string;
  nav: NavItem[];
  footerNote: string;
}

export function Footer({ siteName, tagline, nav, footerNote }: FooterProps) {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)]">
      <div className="mx-auto max-w-7xl px-6 py-14 md:px-10">
        <div className="flex flex-col gap-10 md:flex-row md:justify-between">
          <div className="max-w-sm">
            <div className="flex items-center gap-2 font-[var(--font-display)] text-lg text-[var(--color-text)]">
              <span
                aria-hidden
                className="h-2 w-2 rounded-full bg-[var(--color-gold)]"
              />
              {siteName}
            </div>
            {tagline ? (
              <p className="mt-3 text-xs uppercase tracking-[0.25em] text-[var(--color-gold)]">
                {tagline}
              </p>
            ) : null}
          </div>

          <nav className="grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-3">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-xs uppercase tracking-[0.15em] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-gold)]"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-[var(--color-border)] pt-6 text-xs text-[var(--color-text-muted)] sm:flex-row sm:items-center sm:justify-between">
          <p className="max-w-2xl leading-relaxed">{footerNote}</p>
          <div className="flex items-center gap-4 whitespace-nowrap">
            <Link href="/privacy-policy" className="hover:text-[var(--color-gold)]">
              Privacy Policy
            </Link>
            <Link href="/terms-of-use" className="hover:text-[var(--color-gold)]">
              Terms of Use
            </Link>
            <Link href="/disclaimer" className="hover:text-[var(--color-gold)]">
              Disclaimer
            </Link>
          </div>
        </div>

        <p className="mt-6 text-[11px] text-[var(--color-text-muted)]">
          &copy; {year} {siteName}. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
