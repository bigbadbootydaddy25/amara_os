import Link from "next/link";

export default function NotFound() {
  return (
    <div className="relative flex min-h-[80vh] flex-col items-center justify-center px-6 text-center">
      <span className="font-[var(--font-display)] text-7xl text-[var(--color-gold)]">
        404
      </span>
      <h1 className="mt-4 font-[var(--font-display)] text-2xl text-[var(--color-text)] sm:text-3xl">
        This page could not be found.
      </h1>
      <p className="mt-3 max-w-md text-sm text-[var(--color-text-muted)]">
        The page you are looking for may have been moved or no longer exists.
      </p>
      <Link
        href="/"
        className="mt-8 text-xs font-medium uppercase tracking-[0.2em] text-[var(--color-gold)] hover:text-[var(--color-gold-soft)]"
      >
        &larr; Return Home
      </Link>
    </div>
  );
}
