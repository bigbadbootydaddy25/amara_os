import { cx } from "../lib/cx";

export interface BrandMarkProps {
  fullName: string;
  size?: "sm" | "md";
  className?: string;
}

export function BrandMark({ fullName, size = "md", className }: BrandMarkProps) {
  const avatar = size === "sm" ? "h-10 w-10" : "h-12 w-12";
  const text = size === "sm" ? "text-xs sm:text-sm" : "text-sm sm:text-base";

  return (
    <div className={cx("flex items-center gap-3", className)}>
      <span
        className={cx(
          "flex shrink-0 items-center justify-center rounded-full border border-[var(--color-gold)] bg-[var(--color-bg-elevated)]",
          avatar
        )}
      >
        <CrestMark aria-hidden className="h-[58%] w-[58%] text-[var(--color-gold)]" />
      </span>
      <span
        className={cx(
          "whitespace-nowrap font-[var(--font-display)] font-semibold uppercase tracking-[0.13em] text-[var(--color-text)]",
          text
        )}
      >
        {fullName}
      </span>
    </div>
  );
}

export function CrestMark(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.4} {...props}>
      <path
        d="M4 8.5 5.8 4l2 2.3L12 2l2.2 4.3 2-2.3L18 8.5l-.9 6.4C16.4 18.6 14.5 21 12 22c-2.5-1-4.4-3.4-5.1-7Z"
        strokeLinejoin="round"
      />
      <path
        d="M12 10.5c-2 2.2-4.6 4.1-4.6 6.5a3 3 0 0 0 5 2.2c-.4 1.1-.9 1.9-1.6 2.5h2.4c-.7-.6-1.2-1.4-1.6-2.5a3 3 0 0 0 5-2.2c0-2.4-2.6-4.3-4.6-6.5Z"
        fill="currentColor"
        stroke="none"
      />
    </svg>
  );
}
