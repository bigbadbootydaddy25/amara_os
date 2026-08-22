import Link from "next/link";

export interface FooterProps {
  siteName: string;
  tagline?: string;
  footerNote: string;
}

export function Footer({ siteName, tagline, footerNote }: FooterProps) {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-white/10 py-11 text-sm">
      <div className="mx-auto max-w-[1240px] px-6">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span className="font-[var(--font-display)] text-base uppercase tracking-[0.13em] text-[var(--color-text)]">
              {siteName}
            </span>
            {tagline ? (
              <p className="mt-1 text-xs uppercase tracking-[0.25em] text-[var(--color-gold)]">
                {tagline}
              </p>
            ) : null}
          </div>
          <div className="flex items-center gap-5 whitespace-nowrap text-xs uppercase tracking-[0.12em] text-[#8f887c]">
            <Link href="/privacy-policy" className="transition-colors hover:text-[var(--color-gold)]">
              Privacy Policy
            </Link>
            <Link href="/terms-of-use" className="transition-colors hover:text-[var(--color-gold)]">
              Terms of Use
            </Link>
            <Link href="/disclaimer" className="transition-colors hover:text-[var(--color-gold)]">
              Disclaimer
            </Link>
          </div>
        </div>

        <p className="mt-8 max-w-3xl text-xs leading-relaxed text-[#8f887c]">
          &copy; {year} {siteName}. {footerNote}
        </p>
      </div>
    </footer>
  );
}
