export interface BrandMarkProps {
  shortName: string;
  subtitleColorVar?: string;
  size?: "sm" | "md" | "lg";
}

const sizes = {
  sm: { text: "text-base", crown: "h-2.5 w-3.5 -top-2", subtitle: "text-[9px]" },
  md: { text: "text-xl", crown: "h-3.5 w-5 -top-3", subtitle: "text-[10px]" },
  lg: { text: "text-4xl sm:text-5xl", crown: "h-6 w-8 -top-5", subtitle: "text-xs" },
};

export function BrandMark({ shortName, subtitleColorVar = "var(--color-accent)", size = "md" }: BrandMarkProps) {
  const s = sizes[size];

  return (
    <div className="flex flex-col leading-none">
      <div
        className={`flex items-baseline gap-1.5 font-[var(--font-display)] font-semibold tracking-wide text-[var(--color-text)] ${s.text}`}
      >
        <span>ACES</span>
        <span className="relative inline-flex items-baseline">
          <CrownIcon
            aria-hidden
            className={`absolute left-1/2 -translate-x-1/2 text-[var(--color-gold)] ${s.crown}`}
          />
          N
        </span>
        <span>8S</span>
      </div>
      <span
        className={`mt-1 font-medium uppercase tracking-[0.3em] ${s.subtitle}`}
        style={{ color: subtitleColorVar }}
      >
        {shortName}
      </span>
    </div>
  );
}

function CrownIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 16" fill="currentColor" {...props}>
      <path d="M1 14.5 L2.6 5 L7 9.2 L12 2 L17 9.2 L21.4 5 L23 14.5 Z" />
      <circle cx="12" cy="2" r="1.6" />
      <circle cx="2.6" cy="5" r="1.3" />
      <circle cx="21.4" cy="5" r="1.3" />
      <rect x="0.5" y="14" width="23" height="1.6" rx="0.5" />
    </svg>
  );
}
