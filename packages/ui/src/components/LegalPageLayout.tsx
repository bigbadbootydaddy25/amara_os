import type { LegalSection } from "@aces/content";

export interface LegalPageLayoutProps {
  title: string;
  effectiveDate?: string;
  sections: LegalSection[];
}

export function LegalPageLayout({
  title,
  effectiveDate,
  sections,
}: LegalPageLayoutProps) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-28 md:px-10">
      <span className="text-xs font-medium uppercase tracking-[0.3em] text-[var(--color-gold)]">
        Legal
      </span>
      <h1 className="mt-4 font-[var(--font-display)] text-4xl text-[var(--color-text)] sm:text-5xl">
        {title}
      </h1>
      {effectiveDate ? (
        <p className="mt-4 text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
          Effective {effectiveDate}
        </p>
      ) : null}

      <div className="mt-12 flex flex-col gap-10">
        {sections.map((section) => (
          <div key={section.heading}>
            <h2 className="font-[var(--font-display)] text-xl text-[var(--color-gold)]">
              {section.heading}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-muted)]">
              {section.body}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
