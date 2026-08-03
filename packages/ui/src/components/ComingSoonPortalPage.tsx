import Link from "next/link";
import { AnimatedBackground } from "./AnimatedBackground";

export interface ComingSoonPortalPageProps {
  siteName: string;
  title?: string;
  body?: string;
}

export function ComingSoonPortalPage({
  siteName,
  title = "Private Access Coming Soon",
  body = "This portal is reserved for accredited investors and strategic partners. Secure access is currently in development.",
}: ComingSoonPortalPageProps) {
  return (
    <div className="relative flex min-h-[80vh] items-center justify-center overflow-hidden px-6">
      <AnimatedBackground variant="aurora" />

      <div className="relative z-10 flex max-w-lg flex-col items-center text-center">
        <span
          aria-hidden
          className="mb-6 flex h-14 w-14 items-center justify-center rounded-full border border-[var(--color-gold)]"
        >
          <LockIcon />
        </span>

        <span className="text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
          {siteName}
        </span>

        <h1 className="mt-4 font-[var(--font-display)] text-3xl text-[var(--color-text)] sm:text-4xl">
          {title}
        </h1>

        <p className="mt-4 text-sm leading-relaxed text-[var(--color-text-muted)]">
          {body}
        </p>

        <Link
          href="/"
          className="mt-10 text-xs font-medium uppercase tracking-[0.2em] text-[var(--color-gold)] transition-colors hover:text-[var(--color-gold-soft)]"
        >
          &larr; Return Home
        </Link>
      </div>
    </div>
  );
}

function LockIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--color-gold)"
      strokeWidth="1.5"
      aria-hidden
    >
      <rect x="4" y="11" width="16" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}
