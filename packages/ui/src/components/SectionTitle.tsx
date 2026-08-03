import { cx } from "../lib/cx";

export interface SectionTitleProps {
  eyebrow?: string;
  title: string;
  align?: "left" | "center";
  className?: string;
}

export function SectionTitle({
  eyebrow,
  title,
  align = "left",
  className,
}: SectionTitleProps) {
  return (
    <div
      className={cx(
        "flex flex-col gap-4",
        align === "center" && "items-center text-center",
        className
      )}
    >
      {eyebrow ? (
        <span className="flex items-center gap-3 text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
          <span
            aria-hidden
            className="h-px w-8 bg-[var(--color-gold)]"
          />
          {eyebrow}
        </span>
      ) : null}
      <h2 className="font-[var(--font-display)] text-3xl font-normal leading-tight text-[var(--color-text)] sm:text-4xl md:text-5xl">
        {title}
      </h2>
      <span
        aria-hidden
        className="h-px w-16 bg-gradient-to-r from-[var(--color-gold)] to-transparent"
      />
    </div>
  );
}
